'use strict';
/*
  Characterisation test: plays every game with seeded random choices and hashes everything the rules
  report along the way (layout, status, which cards show, can be picked up, can be tapped or
  double-tapped, which are movable, every legal or illegal move with its error text, the solver's
  candidate moves, ...). The hashes live in test/golden.json. A refactor of the rulesets must leave
  them unchanged; a deliberate change to the rules runs `node test/golden.test.js --update`.
*/
const fs = require('fs');
const vm = require('vm');
const path = require('path');
const crypto = require('crypto');

const html = fs.readFileSync(path.join(__dirname, '..', 'baize.html'), 'utf8');
const grab = id => html.match(new RegExp(`<script id="${id}">([\\s\\S]*?)</script>`))[1];
const ctx = vm.createContext({ structuredClone, console });
const CardSim = vm.runInContext(grab('engine') + '\n;CardSim', ctx);
const { mulberry32, movableCards } = CardSim;

const GAMES = ['klondike', 'freecell', 'golf', 'pyramid', 'spider', 'forty', 'yukon', 'tripeaks'];
const SEEDS = 4;
const STEPS = 40;
const GOLDEN = path.join(__dirname, 'golden.json');

const cards = state => Object.entries(state.piles)
  .map(([id, pile]) => `${id}:${pile.map(e => `${e.card.id}${e.up ? 'u' : 'd'}`).join(',')}`).join('|')
  + JSON.stringify({ ...state, piles: undefined });

/** Every combination of the choices of the options that change play (Random or Winnable does not). */
function optionSets(rules) {
  return rules.options.filter(o => o.id !== 'winnable')
    .reduce((sets, o) => sets.flatMap(set => o.choices.map(c => ({ ...set, [o.id]: c.value }))), [{}])
    .map(set => ({ ...Object.fromEntries(rules.options.map(o => [o.id, o.default])), ...set }));
}

function digestGame(rules) {
  const hash = crypto.createHash('sha1');
  const feed = (...parts) => hash.update(parts.map(p => (typeof p === 'string' ? p : JSON.stringify(p ?? null))).join('\u0001') + '\n');
  const result = (state, action, options) => {
    const r = rules.reduce(state, action, options);
    return r.error ? { error: r.error } : { state: cards(r.state) };
  };

  /** Feed everything the rules say about a position into the hash; return the legal actions found. */
  const observe = (state, options) => {
    feed('state', cards(state), rules.status(state, options), rules.isWon(state), rules.autoAction(state));
    feed('movable', [...movableCards(rules, state, options)].sort());
    feed('moves', rules.moves?.(state, options), rules.progress?.(state), rules.key?.(state));
    const legal = [];
    const piles = Object.entries(state.piles);
    for (const [from, entries] of piles) {
      entries.forEach((entry, index) => {
        feed('cell', from, index, rules.faceUp(state, from, entry, 'viewer'), rules.canPickUp(state, from, index),
          rules.canSelect?.(state, from, index), rules.onTap(state, from, index, null), rules.onActivate(state, from, index));
        for (const [to] of piles) {
          const action = { type: 'move', from, index, to };
          const r = result(state, action, options);
          feed('move', action, r);
          if (r.state) legal.push(action);
        }
      });
      // a tap on an empty pile, and a tap with another card already selected
      feed('tap', from, rules.onTap(state, from, entries.length, null));
      for (const [other, others] of piles) {
        if (!others.length) continue;
        const selection = { pile: other, index: others.length - 1 };
        const tap = rules.onTap(state, from, entries.length - 1, selection);
        feed('tap2', from, other, tap);
        if (tap) { const r = result(state, tap, options); feed('tap2result', r); if (r.state) legal.push(tap); }
      }
    }
    for (const [from, entries] of piles) {
      if (!entries.length) continue;
      for (const action of [rules.onTap(state, from, entries.length - 1, null), rules.onActivate(state, from, entries.length - 1)]) {
        if (!action) continue;
        const r = result(state, action, options);
        feed('act', action, r);
        if (r.state) legal.push(action);
      }
    }
    const auto = rules.autoAction(state);
    if (auto && result(state, auto, options).state) legal.push(auto);
    for (const action of rules.moves?.(state, options) ?? []) if (result(state, action, options).state) legal.push(action);
    return legal;
  };

  for (const options of optionSets(rules)) {
    feed('options', options, rules.layout(options));
    for (let seed = 1; seed <= SEEDS; seed++) {
      const rng = mulberry32(seed * 7919);
      let state = rules.setup(options, mulberry32(seed));
      for (let step = 0; step < STEPS; step++) {
        const legal = observe(state, options);
        if (!legal.length) break;
        const pick = legal[Math.floor(rng() * legal.length)];
        feed('pick', pick);
        state = rules.reduce(state, pick, options).state;
      }
      feed('end', cards(state), rules.isWon(state));
    }
    // Deep positions: walk along a solver's winning line, looking at every fourth position.
    if (rules.canSolve?.(options)) {
      for (let seed = 1; seed <= 3; seed++) {
        let state = rules.setup(options, mulberry32(seed));
        const line = CardSim.solve(rules, options, state, { nodes: 3000 });
        feed('line', line);
        (line ?? []).forEach((action, step) => {
          if (step % 4 === 0) observe(state, options);
          state = rules.reduce(state, action, options).state;
        });
        feed('solved', cards(state), rules.isWon(state));
      }
    }
  }
  return hash.digest('hex');
}

const digests = Object.fromEntries(GAMES.map(id => [id, digestGame(CardSim[id])]));

if (process.argv.includes('--update')) {
  fs.writeFileSync(GOLDEN, JSON.stringify(digests, null, 2) + '\n');
  console.log('golden.json updated');
} else {
  const golden = JSON.parse(fs.readFileSync(GOLDEN, 'utf8'));
  const changed = GAMES.filter(id => golden[id] !== digests[id]);
  if (changed.length) {
    console.error(`golden: the rules of ${changed.join(', ')} behave differently from golden.json`);
    process.exit(1);
  }
  console.log('golden: every game behaves exactly as recorded');
}
