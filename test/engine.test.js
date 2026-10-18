'use strict';
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');

const path = require('path');
const html = fs.readFileSync(process.argv[2] ?? path.join(__dirname, '..', 'baize.html'), 'utf8');
const grab = id => html.match(new RegExp(`<script id="${id}">([\\s\\S]*?)</script>`))[1];
const ctx = vm.createContext({ structuredClone, console });
const CardSim = vm.runInContext(grab('engine') + '\n;CardSim', ctx);
const StandardDeck = vm.runInContext(grab('deck-art') + '\n' + grab('deck') + '\n;StandardDeck', ctx);
const { Session, klondike, freecell, golf, pyramid, fanOffsets, movableCards, mulberry32 } = CardSim;

const FOUNDATIONS = ['f0', 'f1', 'f2', 'f3'];
const TABLEAU = ['t0', 't1', 't2', 't3', 't4', 't5', 't6'];
const red = s => s === 'hearts' || s === 'diamonds';
const opts1 = { draw: 1 };
const opts3 = { draw: 3 };

function checkInvariants(state) {
  const all = Object.values(state.piles).flat();
  assert.strictEqual(all.length, 52, 'card count');
  assert.strictEqual(new Set(all.map(e => e.card.id)).size, 52, 'unique ids');
  assert(state.piles.stock.every(e => !e.up), 'stock face down');
  assert(state.piles.waste.every(e => e.up), 'waste face up');
  for (const id of TABLEAU) {
    const pile = state.piles[id];
    if (pile.length) assert(pile.at(-1).up, `${id} top is up`);
    const firstUp = pile.findIndex(e => e.up);
    assert(pile.slice(firstUp).every(e => e.up), `${id} up cards contiguous`);
    const run = pile.slice(firstUp);
    run.forEach((e, i) => {
      if (i) {
        assert.strictEqual(run[i - 1].card.rank, e.card.rank + 1, `${id} descending`);
        assert.notStrictEqual(red(run[i - 1].card.suit), red(e.card.suit), `${id} alternating`);
      }
    });
  }
  for (const id of FOUNDATIONS) {
    state.piles[id].forEach((e, i) => {
      assert(e.up);
      assert.strictEqual(e.card.rank, i + 1, `${id} ascending`);
      assert.strictEqual(e.card.suit, state.piles[id][0].card.suit, `${id} one suit`);
    });
  }
}

const same = (a, b, msg) => assert.strictEqual(JSON.stringify(a), JSON.stringify(b), msg);
const differs = (a, b) => assert.notStrictEqual(JSON.stringify(a), JSON.stringify(b));
const entry = (suit, rank, up = true) => ({ card: { id: `${suit[0]}${rank}`, suit, rank }, up });
const blank = () => ({ piles: { stock: [], waste: [], f0: [], f1: [], f2: [], f3: [], t0: [], t1: [], t2: [], t3: [], t4: [], t5: [], t6: [] } });
const ok = (state, action, o = opts1) => { const r = klondike.reduce(state, action, o); assert(r.state, `expected legal: ${JSON.stringify(action)} (${r.error})`); return r.state; };
const bad = (state, action, o = opts1) => assert(klondike.reduce(state, action, o).error, `expected illegal: ${JSON.stringify(action)}`);
const move = (from, index, to) => ({ type: 'move', from, index, to });

/* Deal */
{
  const s = klondike.setup(opts1, mulberry32(1));
  checkInvariants(s);
  TABLEAU.forEach((id, i) => assert.strictEqual(s.piles[id].length, i + 1));
  assert.strictEqual(s.piles.stock.length, 24);
  const again = klondike.setup(opts1, mulberry32(1));
  same(again, s, 'same seed, same deal');
  differs(klondike.setup(opts1, mulberry32(2)), s);
}

/* Draw, recycle */
{
  let s = klondike.setup(opts1, mulberry32(5));
  const topId = s.piles.stock.at(-1).card.id;
  s = ok(s, { type: 'draw' });
  assert.strictEqual(s.piles.waste.at(-1).card.id, topId);
  assert(s.piles.waste.at(-1).up);
  let s3 = klondike.setup(opts3, mulberry32(5));
  const [a, b, c] = s3.piles.stock.slice(-3).map(e => e.card.id).reverse();
  s3 = ok(s3, { type: 'draw' }, opts3);
  same(s3.piles.waste.map(e => e.card.id), [a, b, c]);
  assert.strictEqual(s3.piles.stock.length, 21);

  const few = blank();
  few.piles.stock = [entry('spades', 4, false), entry('spades', 5, false)];
  assert.strictEqual(ok(few, { type: 'draw' }, opts3).piles.waste.length, 2);
  bad(few, { type: 'recycle' });

  const spent = blank();
  spent.piles.waste = [entry('hearts', 1), entry('hearts', 2), entry('hearts', 3)];
  const r = ok(spent, { type: 'recycle' });
  assert.strictEqual(r.piles.stock.at(-1).card.id, 'h1', 'first drawn card is drawn again first');
  assert(r.piles.stock.every(e => !e.up));
  bad(blank(), { type: 'draw' });
  bad(blank(), { type: 'recycle' });
}

/* Tableau and foundation rules */
{
  let s = blank();
  s.piles.t0 = [entry('hearts', 6)];
  s.piles.t1 = [entry('spades', 5)];
  s.piles.t2 = [entry('clubs', 5)];
  s.piles.t3 = [entry('hearts', 5)];
  s.piles.t4 = [entry('spades', 4)];
  ok(s, move('t1', 0, 't0'));
  ok(s, move('t2', 0, 't0'));
  bad(s, move('t3', 0, 't0'), 'same colour');
  bad(s, move('t4', 0, 't0'), 'wrong rank');
  bad(s, move('t0', 0, 't0'), 'same pile');
  bad(s, move('t0', 0, 't6'), 'non-king to empty column');
  s.piles.t5 = [entry('diamonds', 13)];
  ok(s, move('t5', 0, 't6'));

  // runs, face-down cards, auto flip
  const r = blank();
  r.piles.t0 = [entry('clubs', 9, false), entry('hearts', 8, true), entry('spades', 7, true)];
  r.piles.t1 = [entry('spades', 9, true)];
  bad(r, move('t0', 0, 't1'), 'face-down card');
  const moved = ok(r, move('t0', 1, 't1'));
  same(moved.piles.t1.map(e => e.card.id), ['s9', 'h8', 's7']);
  assert(moved.piles.t0[0].up, 'auto flip');
  bad(r, move('t0', 2, 't1'), 'seven onto nine');
}

/* Foundations */
{
  let s = blank();
  s.piles.t0 = [entry('hearts', 1)];
  s.piles.t1 = [entry('hearts', 2)];
  s.piles.t2 = [entry('spades', 2)];
  s.piles.t3 = [entry('spades', 1)];
  s = ok(s, move('t0', 0, 'f0'));
  ok(s, move('t1', 0, 'f0'));
  bad(s, move('t2', 0, 'f0'), 'wrong suit');
  bad(s, move('t2', 0, 'f1'), 'two on empty foundation');
  ok(s, move('t3', 0, 'f1'));
  s = ok(s, move('t1', 0, 'f0'));
  // back out
  s.piles.t4 = [entry('clubs', 3)];
  s.piles.t5 = [entry('spades', 3)];
  const back = ok(s, move('f0', 1, 't4'));
  assert.strictEqual(back.piles.t4.at(-1).card.id, 'h2');
  bad(s, move('f0', 0, 'f1'), 'foundation to foundation');
  // waste
  s.piles.waste = [entry('diamonds', 7), entry('clubs', 8)];
  s.piles.t6 = [entry('hearts', 9)];
  ok(s, move('waste', 1, 't6'));
  bad(s, move('waste', 0, 't6'), 'buried waste card');
  bad(s, move('stock', 0, 't6'));
  bad(s, move('t6', 0, 'waste'));
  bad(s, move('nope', 0, 't6'));
  bad(s, move('__proto__', 0, 't6'));
  bad(s, { type: 'toString' });
}

/* Auto actions */
{
  const s = blank();
  s.piles.t0 = [entry('hearts', 2), entry('spades', 1)];
  const noAuto = klondike.autoAction(s);
  assert(noAuto, 'settled position has an auto move');
  s.piles.stock = [entry('clubs', 3, false)];
  assert.strictEqual(klondike.autoAction(s), null, 'not offered while the stock has cards');
  s.piles.stock = [];
  s.piles.t0 = [entry('clubs', 13), entry('hearts', 12)];
  assert.strictEqual(klondike.autoAction(s), null, 'nothing to play');

  // Finishing a settled game by repeated auto actions
  let state = blank();
  for (const suit of ['spades', 'hearts', 'diamonds', 'clubs']) {
    const i = ['spades', 'hearts', 'diamonds', 'clubs'].indexOf(suit);
    state.piles[`t${i}`] = Array.from({ length: 13 }, (_, k) => entry(suit, 13 - k));
  }
  let steps = 0;
  for (let a = klondike.autoAction(state); a; a = klondike.autoAction(state)) {
    state = ok(state, a);
    steps++;
  }
  assert(klondike.isWon(state));
  assert.strictEqual(steps, 52);

  // double tap
  const t = blank();
  t.piles.t0 = [entry('clubs', 5, false), entry('hearts', 1)];
  same(klondike.onActivate(t, 't0', 1), move('t0', 1, 'f0'));
  assert.strictEqual(klondike.onActivate(t, 't0', 0), null);
  assert.strictEqual(klondike.onActivate(t, 'stock', 0), null);
  same(klondike.onTap(blank(), 'stock', 0), null);
}

/* canPickUp */
{
  const s = blank();
  s.piles.t0 = [entry('clubs', 5, false), entry('hearts', 4), entry('spades', 3)];
  s.piles.waste = [entry('hearts', 1), entry('hearts', 2)];
  s.piles.stock = [entry('hearts', 3, false)];
  assert(!klondike.canPickUp(s, 't0', 0));
  assert(klondike.canPickUp(s, 't0', 1));
  assert(klondike.canPickUp(s, 't0', 2));
  assert(!klondike.canPickUp(s, 'waste', 0));
  assert(klondike.canPickUp(s, 'waste', 1));
  assert(!klondike.canPickUp(s, 'stock', 0));
  assert(!klondike.canPickUp(s, 't3', 0));
}

/* Random playouts: invariants hold, undo and replay agree */
{
  let totalMoves = 0, wins = 0;
  for (let seed = 0; seed < 12; seed++) {
    const o = seed % 2 ? opts3 : opts1;
    const session = new Session(klondike, o, seed);
    const rng = mulberry32(seed + 1000);
    for (let step = 0; step < 150 && !session.won; step++) {
      const state = session.state;
      const candidates = [];
      for (const from of ['waste', ...FOUNDATIONS, ...TABLEAU]) {
        state.piles[from].forEach((_, index) => {
          if (!klondike.canPickUp(state, from, index)) return;
          for (const to of [...FOUNDATIONS, ...TABLEAU]) {
            if (klondike.reduce(state, move(from, index, to), o).state) candidates.push(move(from, index, to));
          }
        });
      }
      const tap = klondike.onTap(state, 'stock', 0);
      if (tap) candidates.push(tap);
      if (!candidates.length) break;
      // prefer moves to foundations and from the tableau for a more interesting walk
      const pick = candidates[Math.floor(rng() * candidates.length)];
      assert(session.apply(pick));
      totalMoves++;
      checkInvariants(session.state);
    }
    if (session.won) wins++;
    const replay = new Session(klondike, o, seed, session.actions);
    same(replay.state, session.state, 'replay matches');
    // undo all the way back
    const total = session.actions.length;
    for (let i = 0; i < total; i++) assert(session.undo());
    same(session.state, klondike.setup(o, mulberry32(seed)), 'undo restores the deal');
    assert(!session.undo());
  }
  console.log(`random playouts: ${totalMoves} moves checked, ${wins} wins`);
}

/* A saved game with an illegal action is rejected */
assert.throws(() => new Session(klondike, opts1, 3, [move('t0', 0, 't1')]));

/* Fan geometry */
{
  const slot = { fan: 'down', visible: Infinity, limit: 3.8 };
  const pile = Array.from({ length: 19 }, (_, i) => ({ up: i >= 6 }));
  const offsets = fanOffsets(slot, pile, e => e.up);
  assert(offsets.at(-1) <= 2.8 + 1e-9, 'squeezed to fit');
  assert(offsets.every((o, i) => i === 0 || o > offsets[i - 1]), 'still increasing');
  const short = fanOffsets(slot, [{ up: false }, { up: true }, { up: true }], e => e.up);
  same(short.map(o => +o.toFixed(2)), [0, 0.1, 0.36]);
  const waste = fanOffsets({ fan: 'right', visible: 3 }, [1, 2, 3, 4, 5].map(() => ({ up: true })), e => e.up);
  same(waste.map(o => +o.toFixed(2)), [0, 0, 0, 0.22, 0.44]);
  same(fanOffsets({ fan: 'none' }, [{}, {}], () => true), [0, 0]);
  same(fanOffsets(slot, [], () => true), []);
}

/* Movable cards */
{
  const ids = (rules, state, o = opts1) => [...movableCards(rules, state, o)].sort().join(',');

  // Klondike: a run moves as a unit; buried and blocked cards do not
  const k = blank();
  k.piles.t0 = [entry('clubs', 9, false), entry('hearts', 8), entry('spades', 7)];   // 8H+7S can go on a black 9
  k.piles.t1 = [entry('spades', 9)];
  k.piles.t2 = [entry('diamonds', 3)];                                                // nowhere to go
  k.piles.t3 = [entry('hearts', 1)];                                                  // ace goes home
  k.piles.waste = [entry('clubs', 12), entry('hearts', 2)];                           // top waste card is blocked; 12C is buried
  same(ids(klondike, k), 'h1,h8,s7', 'run and ace');

  k.piles.stock = [entry('clubs', 5, false)];
  assert(movableCards(klondike, k, opts1).has('c5'), 'top stock card can be tapped');
  k.piles.stock = [];
  assert(!movableCards(klondike, k, opts1).has('c5'));
  k.piles.waste = [entry('hearts', 1)];
  k.piles.t3 = [];
  assert(movableCards(klondike, k, opts1).has('h1'), 'waste card that can go home');
  k.piles.stock = []; k.piles.waste = [entry('clubs', 5)];
  assert(!movableCards(klondike, k, opts1).has('c5'), 'waste with an empty stock cannot be recycled');
  k.piles.waste = [];
  assert(klondike.reduce(k, { type: 'recycle' }, opts1).error);

  // FreeCell: with every cell full and nothing building, nothing is movable
  const f = freecell.setup({}, mulberry32(1));
  for (const id of Object.keys(f.piles)) f.piles[id] = [];
  f.piles.c0 = [entry('spades', 13)]; f.piles.c1 = [entry('spades', 12)];
  f.piles.c2 = [entry('spades', 11)]; f.piles.c3 = [entry('spades', 10)];
  f.piles.t0 = [entry('hearts', 5)];
  f.piles.t1 = [entry('clubs', 7)];
  ['t2', 't3', 't4', 't5', 't6', 't7'].forEach((id, i) => { f.piles[id] = [entry('diamonds', 9 - i)]; });
  const fc2 = JSON.parse(JSON.stringify(f));
  fc2.piles.t2 = [entry('diamonds', 6)];      // 5H can go on 6D? same colour: no. 6D accepts a black 5
  fc2.piles.t3 = [entry('clubs', 5)];         // 5C onto 6D
  assert(movableCards(freecell, fc2, {}).has('c5'), '5C goes onto the red six');
  assert(!movableCards(freecell, fc2, {}).has('h5'), '5H cannot go on the red six');
  // an empty column makes every top card movable
  fc2.piles.t7 = [];
  assert(movableCards(freecell, fc2, {}).has('h5'), 'anything can go to an empty column');
  // cards in a cell come back out
  fc2.piles.t6 = [entry('hearts', 11)];
  assert(movableCards(freecell, fc2, {}).has('s10'), 'cell card can leave');

  // never throws on a fresh deal, and finds at least one move in nearly every deal
  let withMoves = 0;
  for (let seed = 0; seed < 40; seed++) {
    for (const [rules, o] of [[klondike, opts1], [freecell, {}]]) {
      const st = rules.setup(o, mulberry32(seed));
      const m = movableCards(rules, st, o);
      for (const id of m) assert(Object.values(st.piles).flat().some(e => e.card.id === id));
      if (m.size) withMoves++;
    }
  }
  assert(withMoves >= 78, `moves found in ${withMoves}/80 deals`);
}

/* Golf */
{
  const COLS = ['t0', 't1', 't2', 't3', 't4', 't5', 't6'];
  const g = () => { const st = golf.setup({ wrap: 0 }, mulberry32(1)); for (const id of Object.keys(st.piles)) st.piles[id] = []; return st; };
  const gok = (state, action, o = { wrap: 0 }) => { const r = golf.reduce(state, action, o); assert(r.state, `expected legal: ${JSON.stringify(action)} (${r.error})`); return r.state; };
  const gbad = (state, action, why, o = { wrap: 0 }) => assert(golf.reduce(state, action, o).error, `expected illegal: ${why}`);
  const play = from => ({ type: 'play', from });
  const showing = state => state.piles.waste.at(-1).card.id;

  // deal
  const dealt = golf.setup({ wrap: 0 }, mulberry32(3));
  const every = Object.values(dealt.piles).flat();
  assert.strictEqual(every.length, 52);
  assert.strictEqual(new Set(every.map(e => e.card.id)).size, 52);
  COLS.forEach(id => { assert.strictEqual(dealt.piles[id].length, 5); assert(dealt.piles[id].every(e => e.up)); });
  assert.strictEqual(dealt.piles.waste.length, 1);
  assert(dealt.piles.waste[0].up);
  assert.strictEqual(dealt.piles.stock.length, 16);
  assert(dealt.piles.stock.every(e => !e.up));
  same(golf.setup({ wrap: 0 }, mulberry32(3)), dealt);

  // play: one rank up or down, from the last card only
  let s = g();
  s.piles.waste = [entry('hearts', 7)];
  s.piles.t0 = [entry('clubs', 2), entry('spades', 8)];
  s.piles.t1 = [entry('clubs', 9)];
  s.piles.t2 = [entry('clubs', 7)];
  s.piles.t3 = [entry('clubs', 13)];
  s.piles.t4 = [entry('diamonds', 1)];
  gbad(s, play('t1'), 'two ranks away');
  gbad(s, play('t2'), 'same rank');
  gbad(s, play('t5'), 'empty column');
  gbad(s, play('stock'), 'not a column');
  gbad(s, play('waste'), 'not a column');
  gbad(s, play('__proto__'), 'unknown pile');
  gbad(s, { type: 'move', from: 't0', index: 1, to: 'waste' }, 'dragging is not a Golf action');
  s = gok(s, play('t0'));                         // 8 onto 7
  assert.strictEqual(showing(s), 's8');
  assert.strictEqual(s.piles.t0.length, 1);
  gbad(s, play('t0'), '2 onto 8');
  s = gok(s, play('t1'));                         // 9 onto 8, upward
  gbad(s, play('t2'), '7 onto 9');
  s.piles.waste.push(entry('hearts', 8));
  s = gok(s, play('t2'));                         // and back down: 7 onto 8
}

/* Golf: wrap, draw, win, taps, highlights, playouts */
{
  const COLS = ['t0', 't1', 't2', 't3', 't4', 't5', 't6'];
  const g = () => { const st = golf.setup({ wrap: 0 }, mulberry32(1)); for (const id of Object.keys(st.piles)) st.piles[id] = []; return st; };
  const play = from => ({ type: 'play', from });
  const reduce = (state, action, o = { wrap: 0 }) => golf.reduce(state, action, o);

  // wrap: kings and aces are neighbours only when asked
  const w = g();
  w.piles.waste = [entry('hearts', 13)];
  w.piles.t0 = [entry('clubs', 1)];
  assert(reduce(w, play('t0'), { wrap: 0 }).error);
  assert(reduce(w, play('t0'), { wrap: 1 }).state);
  w.piles.waste = [entry('hearts', 1)];
  w.piles.t0 = [entry('clubs', 13)];
  assert(reduce(w, play('t0'), { wrap: 0 }).error);
  assert(reduce(w, play('t0'), { wrap: 1 }).state);
  w.piles.t0 = [entry('clubs', 12)];
  assert(reduce(w, play('t0'), { wrap: 1 }).error, 'queen is not next to an ace');

  // draw
  const d = g();
  d.piles.waste = [entry('hearts', 5)];
  d.piles.stock = [entry('clubs', 3, false), entry('spades', 4, false)];
  const drawn = reduce(d, { type: 'draw' }).state;
  assert.strictEqual(drawn.piles.waste.at(-1).card.id, 's4');
  assert(drawn.piles.waste.at(-1).up);
  assert.strictEqual(drawn.piles.stock.length, 1);
  d.piles.stock = [];
  assert(reduce(d, { type: 'draw' }).error);
  assert(reduce(d, { type: 'recycle' }).error, 'no redeal in Golf');

  // taps
  const t = g();
  t.piles.waste = [entry('hearts', 5)];
  t.piles.t0 = [entry('clubs', 9), entry('spades', 6)];
  t.piles.stock = [entry('clubs', 3, false)];
  same(golf.onTap(t, 't0', 1), play('t0'));
  assert.strictEqual(golf.onTap(t, 't0', 0), null, 'only the last card');
  assert.strictEqual(golf.onTap(t, 't0', -1), null);
  assert.strictEqual(golf.onTap(t, 't3', -1), null, 'empty column');
  same(golf.onTap(t, 'stock', 0), { type: 'draw' });
  assert.strictEqual(golf.onTap(t, 'waste', 0), null);
  t.piles.stock = [];
  assert.strictEqual(golf.onTap(t, 'stock', -1), null);
  assert(!golf.canPickUp(t, 't0', 1), 'nothing is dragged in Golf');

  // highlights: playable column cards and the top of the stock
  const h = g();
  h.piles.waste = [entry('hearts', 5)];
  h.piles.t0 = [entry('clubs', 9), entry('spades', 6)];
  h.piles.t1 = [entry('clubs', 4)];
  h.piles.t2 = [entry('clubs', 11)];
  h.piles.stock = [entry('clubs', 3, false), entry('diamonds', 2, false)];
  same([...movableCards(golf, h, { wrap: 0 })].sort(), ['c4', 'd2', 's6']);
  h.piles.stock = [];
  same([...movableCards(golf, h, { wrap: 0 })].sort(), ['c4', 's6']);

  // win
  const win = g();
  win.piles.waste = [entry('hearts', 5)];
  assert(golf.isWon(win));
  win.piles.t6 = [entry('clubs', 6)];
  assert(!golf.isWon(win));

  // random playouts: invariants, replay, undo
  let wins = 0;
  for (let seed = 0; seed < 60; seed++) {
    const o = { wrap: seed % 2 };
    const session = new Session(golf, o, seed);
    const rng = mulberry32(seed + 5);
    for (let step = 0; step < 200 && !session.won; step++) {
      const choices = COLS.map(id => golf.onTap(session.state, id, session.state.piles[id].length - 1))
        .filter(a => a && golf.reduce(session.state, a, o).state);
      const draw = golf.onTap(session.state, 'stock', 0);
      if (draw) choices.push(draw);
      if (!choices.length) break;
      assert(session.apply(choices[Math.floor(rng() * choices.length)]));
      const cards = Object.values(session.state.piles).flat();
      assert.strictEqual(cards.length, 52);
      assert.strictEqual(new Set(cards.map(e => e.card.id)).size, 52);
      assert(session.state.piles.waste.length >= 1 && session.state.piles.waste.every(e => e.up));
    }
    if (session.won) wins++;
    const replay = new Session(golf, o, seed, session.actions);
    same(replay.state, session.state, 'replay matches');
    while (session.undo());
    same(session.state, golf.setup(o, mulberry32(seed)), 'undo restores the deal');
  }
  console.log(`golf playouts: ${wins} wins of 60`);
}

/* Pyramid */
{
  const rowIds = r => Array.from({ length: r + 1 }, (_, i) => `p${r}_${i}`);
  const ALL = [0, 1, 2, 3, 4, 5, 6].flatMap(rowIds);
  const o2 = { redeals: 2 };
  const blankPy = () => {
    const st = pyramid.setup(o2, mulberry32(1));
    for (const id of Object.keys(st.piles)) st.piles[id] = [];
    return st;
  };
  const pok = (state, action, o = o2) => { const r = pyramid.reduce(state, action, o); assert(r.state, `expected legal: ${JSON.stringify(action)} (${r.error})`); return r.state; };
  const pbad = (state, action, why, o = o2) => assert(pyramid.reduce(state, action, o).error, `expected illegal: ${why}`);
  const take = (...from) => ({ type: 'take', from });
  const idsOf = (st, o = o2) => [...movableCards(pyramid, st, o)].sort();

  // deal
  const dealt = pyramid.setup(o2, mulberry32(4));
  const all = Object.values(dealt.piles).flat();
  assert.strictEqual(all.length, 52);
  assert.strictEqual(new Set(all.map(e => e.card.id)).size, 52);
  ALL.forEach(id => { assert.strictEqual(dealt.piles[id].length, 1); assert(dealt.piles[id][0].up); });
  assert.strictEqual(dealt.piles.stock.length, 24);
  assert(dealt.piles.stock.every(e => !e.up));
  assert.strictEqual(dealt.piles.waste.length, 0);
  assert.strictEqual(dealt.piles.out.length, 0);
  assert.strictEqual(dealt.redeals, 0);
  same(pyramid.setup(o2, mulberry32(4)), dealt);
  // only the bottom row is free at the start
  ALL.forEach(id => assert.strictEqual(pyramid.canSelect(dealt, id, 0), id.startsWith('p6_'), id));

  // pairs and kings
  let s = blankPy();
  s.piles.p6_0 = [entry('hearts', 6)];
  s.piles.p6_1 = [entry('spades', 7)];
  s.piles.p6_2 = [entry('clubs', 7)];
  s.piles.p6_3 = [entry('clubs', 13)];
  s.piles.p6_4 = [entry('clubs', 12)];
  s.piles.p6_5 = [entry('diamonds', 1)];
  s.piles.p5_0 = [entry('diamonds', 5)];          // overlapped by p6_0 and p6_1
  pbad(s, take('p6_0'), 'a six alone');
  pbad(s, take('p6_0', 'p6_0'), 'the same card twice');
  pbad(s, take('p6_0', 'p6_1', 'p6_2'), 'three cards');
  pbad(s, take(), 'no cards');
  pbad(s, take('p6_1', 'p6_2'), '7 + 7');
  pbad(s, take('p5_0', 'p6_5'), 'a covered card');
  pbad(s, take('stock'), 'not a takeable pile');
  pbad(s, take('out', 'p6_0'), 'unknown or closed pile');
  pbad(s, take('__proto__'), 'prototype key');
  pbad(s, { type: 'take', from: 'p6_3' }, 'from must be a list');
  pbad(s, { type: 'move', from: 'p6_3', index: 0, to: 'waste' }, 'dragging is not a Pyramid action');
  let t = pok(s, take('p6_3'));                   // king alone
  assert.strictEqual(t.piles.p6_3.length, 0);
  assert.strictEqual(t.piles.out.at(-1).card.id, 'c13');
  t = pok(t, take('p6_4', 'p6_5'));               // queen + ace
  assert.strictEqual(t.piles.out.length, 3);
  t = pok(t, take('p6_1', 'p6_0'));  // 6 + 7, in either order
  assert.strictEqual(t.piles.p5_0.length, 1);
  assert(pyramid.canSelect(t, 'p5_0', 0), 'uncovered once both cards below are gone');
  const u = pok(s, take('p6_0', 'p6_1'));
  assert(pyramid.canSelect(u, 'p5_0', 0));
  const half = pok(s, take('p6_5', 'p6_4'));
  assert(!pyramid.canSelect(half, 'p5_0', 0), 'still overlapped by p6_0 and p6_1');

  // the waste takes part, and only its top card
  const w = blankPy();
  w.piles.p6_0 = [entry('hearts', 4)];
  w.piles.waste = [entry('clubs', 9), entry('spades', 9)];
  const w2 = pok(w, take('waste', 'p6_0'));
  assert.strictEqual(w2.piles.waste.length, 1);
  assert.strictEqual(w2.piles.waste[0].card.id, 'c9', 'the card beneath is left');
  w.piles.waste = [entry('spades', 13)];
  const w3 = pok(w, take('waste'));
  assert.strictEqual(w3.piles.waste.length, 0);
  assert(!pyramid.canSelect(w, 'waste', 5));

  // draw and redeals
  const d = blankPy();
  d.piles.stock = [entry('clubs', 2, false), entry('spades', 3, false)];
  let dd = pok(d, { type: 'draw' });
  assert.strictEqual(dd.piles.waste.at(-1).card.id, 's3');
  assert(dd.piles.waste.at(-1).up);
  pbad(dd, { type: 'recycle' }, 'stock is not empty');
  dd = pok(dd, { type: 'draw' });
  pbad(dd, { type: 'draw' }, 'empty stock');
  let r1 = pok(dd, { type: 'recycle' });
  assert.strictEqual(r1.piles.stock.length, 2);
  assert.strictEqual(r1.piles.stock.at(-1).card.id, 's3', 'the first card drawn comes round first again');
  assert(r1.piles.stock.every(e => !e.up));
  assert.strictEqual(r1.redeals, 1);
  let r2 = pok(pok(pok(r1, { type: 'draw' }), { type: 'draw' }), { type: 'recycle' });
  assert.strictEqual(r2.redeals, 2);
  const r3 = pok(pok(r2, { type: 'draw' }), { type: 'draw' });
  pbad(r3, { type: 'recycle' }, 'third redeal with Two allowed');
  pok(r3, { type: 'recycle' }, { redeals: 99 });
  pbad(blankPy(), { type: 'recycle' }, 'nothing to turn over');

  // taps
  const tp = blankPy();
  tp.piles.p6_0 = [entry('hearts', 6)];
  tp.piles.p6_1 = [entry('spades', 7)];
  tp.piles.p6_2 = [entry('clubs', 13)];
  tp.piles.p5_0 = [entry('clubs', 2)];
  tp.piles.stock = [entry('clubs', 3, false)];
  same(pyramid.onTap(tp, 'stock', 0), { type: 'draw' });
  same(pyramid.onTap(tp, 'p6_2', 0), take('p6_2'), 'a king goes at once');
  assert.strictEqual(pyramid.onTap(tp, 'p6_0', 0, null), null, 'first card of a pair only selects');
  same(pyramid.onTap(tp, 'p6_1', 0, { pile: 'p6_0', index: 0 }), take('p6_0', 'p6_1'));
  assert.strictEqual(pyramid.onTap(tp, 'p6_0', 0, { pile: 'p6_0', index: 0 }), null, 'same card again');
  assert.strictEqual(pyramid.onTap(tp, 'p5_0', 0, null), null, 'covered card');
  assert.strictEqual(pyramid.onTap(tp, 'p4_0', 0), null, 'empty position');
  tp.piles.stock = [];
  assert.strictEqual(pyramid.onTap(tp, 'stock', -1), null);
  tp.piles.waste = [entry('clubs', 4)];
  same(pyramid.onTap(tp, 'stock', -1), { type: 'recycle' });
  assert(!pyramid.canPickUp(tp, 'p6_0', 0), 'nothing is dragged');

  // highlights: kings, pairs, and the top of the stock
  const h = blankPy();
  h.piles.p6_0 = [entry('hearts', 6)];
  h.piles.p6_1 = [entry('spades', 7)];
  h.piles.p6_2 = [entry('clubs', 9)];
  h.piles.p6_3 = [entry('clubs', 13)];
  h.piles.p5_0 = [entry('diamonds', 4)];          // would pair with the nine, but is covered
  h.piles.waste = [entry('diamonds', 2)];
  same(idsOf(h), ['c13', 'h6', 's7']);
  h.piles.waste = [entry('diamonds', 4)];
  same(idsOf(h), ['c13', 'c9', 'd4', 'h6', 's7'], 'waste four pairs with the nine');
  h.piles.stock = [entry('spades', 2, false), entry('hearts', 3, false)];
  assert(idsOf(h).includes('h3'), 'top of the stock can be tapped');
  assert(!idsOf(h).includes('s2'));

  // status and win
  const st = pyramid.status(dealt, o2);
  same(st.map(x => x.value), ['28 / 28', 24, 2]);
  same(pyramid.status(r1, o2).map(x => x.value), ['0 / 28', 2, 1]);
  assert.strictEqual(pyramid.status(dealt, { redeals: 99 })[2].value, 'unlimited');
  assert(pyramid.isWon(blankPy()));
  assert(!pyramid.isWon(h));

  // random playouts: invariants, replay, undo
  let wins = 0;
  for (let seed = 0; seed < 40; seed++) {
    const o = { redeals: seed % 2 ? 99 : 2 };
    const session = new Session(pyramid, o, seed);
    const rng = mulberry32(seed + 9);
    for (let step = 0; step < 250 && !session.won; step++) {
      const state = session.state;
      const open = [...ALL, 'waste'].filter(id => state.piles[id].length && pyramid.canSelect(state, id, state.piles[id].length - 1));
      const choices = [];
      for (const a of open) {
        choices.push(take(a));
        for (const b of open) if (a < b) choices.push(take(a, b));
      }
      choices.push({ type: 'draw' }, { type: 'recycle' });
      const legal = choices.filter(a => pyramid.reduce(state, a, o).state);
      if (!legal.length) break;
      assert(session.apply(legal[Math.floor(rng() * legal.length)]));
      const cards = Object.values(session.state.piles).flat();
      assert.strictEqual(cards.length, 52);
      assert.strictEqual(new Set(cards.map(e => e.card.id)).size, 52);
      assert(session.state.redeals <= o.redeals);
    }
    if (session.won) wins++;
    same(new Session(pyramid, o, seed, session.actions).state, session.state, 'replay matches');
    while (session.undo());
    same(session.state, pyramid.setup(o, mulberry32(seed)), 'undo restores the deal');
  }
  console.log(`pyramid playouts: ${wins} wins of 40`);
}

/* Deck artwork */
{
  const ids = [];
  for (const suit of ['spades', 'hearts', 'diamonds', 'clubs']) {
    for (let rank = 1; rank <= 13; rank++) {
      const svg = StandardDeck.face({ id: 'x', suit, rank });
      assert(svg && svg.startsWith('<svg') && svg.endsWith('</svg>'), `${suit} ${rank} art`);
      assert(svg.includes('viewBox="-120 -168 240 336"'), 'common viewBox');
      assert(!/<script|onload|href="http/i.test(svg), 'no active content');
      ids.push(...(svg.match(/ id="[^"]+"/g) || []));
    }
  }
  assert.strictEqual(new Set(ids).size, ids.length, 'element ids are unique across the deck');
  assert.strictEqual(StandardDeck.label({ suit: 'hearts', rank: 12 }), 'Queen of hearts');
  assert.strictEqual(StandardDeck.label({ suit: 'clubs', rank: 7 }), '7 of clubs');
}

/* FreeCell */
{
  const FC_COLS = ['t0', 't1', 't2', 't3', 't4', 't5', 't6', 't7'];
  const CELLS = ['c0', 'c1', 'c2', 'c3'];
  const fc = () => { const s = freecell.setup({}, mulberry32(1)); for (const id of Object.keys(s.piles)) s.piles[id] = []; return s; };
  const fok = (state, action) => { const r = freecell.reduce(state, action, {}); assert(r.state, `expected legal: ${JSON.stringify(action)} (${r.error})`); return r.state; };
  const fbad = (state, action, why) => assert(freecell.reduce(state, action, {}).error, `expected illegal: ${why}`);
  const run = (...ranks) => ranks.map(([suit, rank]) => entry(suit, rank));

  // deal
  const dealt = freecell.setup({}, mulberry32(7));
  assert.strictEqual(Object.values(dealt.piles).flat().length, 52);
  assert.strictEqual(new Set(Object.values(dealt.piles).flat().map(e => e.card.id)).size, 52);
  assert(Object.values(dealt.piles).flat().every(e => e.up), 'all face up');
  FC_COLS.forEach((id, i) => assert.strictEqual(dealt.piles[id].length, i < 4 ? 7 : 6));
  same(freecell.setup({}, mulberry32(7)), dealt);

  // cells
  let s = fc();
  s.piles.t0 = run(['spades', 9], ['hearts', 8]);
  s.piles.t1 = run(['clubs', 4]);
  s = fok(s, move('t0', 1, 'c0'));
  fbad(s, move('t1', 0, 'c0'), 'occupied cell');
  s = fok(s, move('t1', 0, 'c1'));
  assert.strictEqual(s.piles.t1.length, 0);
  fbad(s, move('c0', 0, 'c2') && { type: 'move', from: 'c0', index: 1, to: 'c2' }, 'no such card');
  s = fok(s, move('c0', 0, 't0'));        // 8H back on 9S
  assert.strictEqual(s.piles.t0.length, 2);
  s = fok(s, move('c1', 0, 't1'));        // anything goes on an empty column
  fbad(s, move('f0', 0, 't2'), 'foundation is closed');

  // foundations from cells and columns
  let f = fc();
  f.piles.t0 = run(['hearts', 1]);
  f.piles.c0 = run(['hearts', 2]);
  f.piles.t1 = run(['spades', 2]);
  f = fok(f, move('t0', 0, 'f0'));
  f = fok(f, move('c0', 0, 'f0'));
  fbad(f, move('t1', 0, 'f0'), 'wrong suit');
  fbad(f, move('t1', 0, 'f1'), 'two on an empty foundation');
  fbad(f, move('f0', 1, 't1'), 'cannot take back');

  // run length limits: (empty cells + 1) * 2^(empty columns other than the target)
  const build = (cellsFilled, emptyCols, runLen, targetEmpty) => {
    const st = fc();
    const ranks = Array.from({ length: runLen }, (_, i) => [i % 2 ? 'hearts' : 'spades', runLen + 1 - i]);
    st.piles.t0 = run(['clubs', 13], ...ranks);
    st.piles.t1 = targetEmpty ? [] : run(['diamonds', runLen + 2]);
    const spare = FC_COLS.slice(2);
    spare.forEach((id, i) => { st.piles[id] = i < spare.length - emptyCols ? run(['clubs', 12 - i]) : []; });
    CELLS.slice(0, cellsFilled).forEach((id, i) => { st.piles[id] = run(['diamonds', 1 + i]); });
    return st;
  };
  // 4 free cells, no empty columns: 5 cards
  let st = build(0, 0, 5, false);
  fok(st, move('t0', 1, 't1'));
  fbad(build(0, 0, 6, false), move('t0', 1, 't1'), '6 > 5');
  // 2 free cells, no empty columns: 3 cards
  fok(build(2, 0, 3, false), move('t0', 1, 't1'));
  fbad(build(2, 0, 4, false), move('t0', 1, 't1'), '4 > 3');
  // no cells, one empty column: 2 cards; two empty columns: 4 cards
  fok(build(4, 1, 2, false), move('t0', 1, 't1'));
  fbad(build(4, 1, 3, false), move('t0', 1, 't1'), '3 > 2');
  fok(build(4, 2, 4, false), move('t0', 1, 't1'));
  fbad(build(4, 2, 5, false), move('t0', 1, 't1'), '5 > 4');
  // moving into an empty column does not count that column as a stepping stone
  fok(build(0, 0, 5, true), move('t0', 1, 't1'));
  fbad(build(0, 0, 6, true), move('t0', 1, 't1'), '6 > 5 into an empty column');
  // ...but a second empty column does
  fok(build(0, 1, 10, true), move('t0', 1, 't1'));
  fbad(build(0, 1, 11, true), move('t0', 1, 't1'), '11 > 10');
  // a cell takes one card only; broken runs never move
  fbad(build(0, 0, 3, false), move('t0', 1, 'c0'), 'run into a cell');
  const broken = fc();
  broken.piles.t0 = run(['spades', 9], ['spades', 8]);
  broken.piles.t1 = run(['hearts', 10]);
  fbad(broken, move('t0', 0, 't1'), 'same colour is not a run');
  assert(!freecell.canPickUp(broken, 't0', 0));
  assert(freecell.canPickUp(broken, 't0', 1));

  // double tap: home first, then a free cell
  const d = fc();
  d.piles.t0 = run(['clubs', 9], ['hearts', 1]);
  d.piles.t1 = run(['clubs', 5]);
  same(freecell.onActivate(d, 't0', 1), move('t0', 1, 'f0'));
  same(freecell.onActivate(d, 't1', 0), move('t1', 0, 'c0'));
  assert.strictEqual(freecell.onActivate(d, 't0', 0), null, 'only the top card');
  d.piles.c0 = run(['spades', 5]);
  same(freecell.onActivate(d, 't1', 0), move('t1', 0, 'c1'));
  same(freecell.onActivate(d, 'c0', 0), null, 'a cell card with nowhere to go');

  // auto-finish only when every column runs downward, and then it always finishes
  const a = fc();
  a.piles.t0 = run(['spades', 13], ['hearts', 12], ['spades', 11]);
  a.piles.t1 = run(['spades', 2], ['clubs', 5]);
  assert.strictEqual(freecell.autoAction(a), null, 'column out of order');
  let fin = fc();
  ['spades', 'hearts', 'diamonds', 'clubs'].forEach((suit, i) => {
    fin.piles[FC_COLS[i]] = Array.from({ length: 12 }, (_, k) => entry(suit, 13 - k));
    fin.piles[CELLS[i]] = run([suit, 1]);
  });
  let steps = 0;
  for (let act = freecell.autoAction(fin); act; act = freecell.autoAction(fin)) { fin = fok(fin, act); steps++; }
  assert(freecell.isWon(fin));
  assert.strictEqual(steps, 52);

  // random playouts
  const allCards = state => Object.values(state.piles).flat();
  for (let seed = 0; seed < 8; seed++) {
    const session = new Session(freecell, {}, seed);
    const rng = mulberry32(seed + 77);
    for (let step = 0; step < 120 && !session.won; step++) {
      const state = session.state;
      const options = [];
      for (const from of [...CELLS, ...FC_COLS]) {
        state.piles[from].forEach((_, index) => {
          if (!freecell.canPickUp(state, from, index)) return;
          for (const to of [...CELLS, ...CELLS.length ? ['f0', 'f1', 'f2', 'f3'] : [], ...FC_COLS]) {
            if (freecell.reduce(state, move(from, index, to), {}).state) options.push(move(from, index, to));
          }
        });
      }
      if (!options.length) break;
      assert(session.apply(options[Math.floor(rng() * options.length)]));
      const cards = allCards(session.state);
      assert.strictEqual(new Set(cards.map(e => e.card.id)).size, 52);
      assert(CELLS.every(id => session.state.piles[id].length <= 1), 'cells hold at most one card');
    }
    const replay = new Session(freecell, {}, seed, session.actions);
    same(replay.state, session.state, 'replay matches');
    while (session.undo());
    same(session.state, freecell.setup({}, mulberry32(seed)), 'undo restores the deal');
  }
}

console.log('all tests passed');
