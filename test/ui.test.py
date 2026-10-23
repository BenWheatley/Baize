"""Browser checks for baize.html (needs Python Playwright with Chromium).

Run from anywhere:  python3 test/ui.test.py [check_name ...]
"""
import pathlib
import sys
import traceback
from playwright.sync_api import sync_playwright

URL = (pathlib.Path(__file__).resolve().parent.parent / 'baize.html').as_uri()
GAMES = {'klondike': '0', 'freecell': '1', 'golf': '2', 'pyramid': '3', 'spider': '4', 'forty': '5', 'yukon': '6', 'tripeaks': '7'}
FACE_DOWN = 'Face-down card'

# Deals are fixed so that the checks do not depend on luck. Seed 1 of FreeCell has three
# movable aces; seed 14 of Golf has two playable column cards; seed 2 of Pyramid has exactly one
# pair (queen and ace of spades) and one king (hearts) in the free bottom row; seed 30 of Spider
# (one suit) has exactly one tap-move: the six of spades onto the seven; seed 8 of Forty Thieves
# has exactly one, the two of hearts onto the three, and no ace showing.
SEEDS = {'klondike': 7, 'freecell': 1, 'golf': 14, 'pyramid': 2, 'spider': 30, 'forty': 8, 'yukon': 3, 'tripeaks': 5}


def status(pg):
    return pg.evaluate("document.getElementById('status').innerText.replace(/\\s+/g,' ')")


def count(pg, cls):
    return pg.locator(f'.card.{cls}').count()


def lit(pg):
    return sorted(pg.evaluate("[...document.querySelectorAll('.card.hint')].map(c => c.getAttribute('aria-label'))"))


def open_game(pg, name):
    pg.select_option('#game', GAMES[name])
    pg.wait_for_timeout(900)


def start(pg, name):
    """Replace the saved game of one ruleset with its fixed deal, and open it."""
    pg.evaluate("""([game, seed]) => localStorage.setItem('baize.v2', JSON.stringify(
        { current: game, games: { [game]: { options: {}, seed, actions: [] } } }))""", [name, SEEDS[name]])
    pg.reload()
    pg.wait_for_timeout(800)


def shift(pg, down):
    (pg.keyboard.down if down else pg.keyboard.up)('Shift')
    pg.wait_for_timeout(120)


def tap(pg, selector, where=0.5, wait=300):
    """Click the middle of an element, `where` of the way down it, and let the move settle."""
    b = pg.locator(selector).bounding_box()
    pg.mouse.click(b['x'] + b['width'] / 2, b['y'] + b['height'] * where)
    pg.wait_for_timeout(wait)


def wait_for_deal(pg):
    """Wait until a redeal (cards gathered, then dealt out) has finished."""
    pg.wait_for_timeout(100)
    pg.wait_for_function("!document.getElementById('board').dataset.dealing", timeout=10000)
    pg.wait_for_timeout(300)


def check_menu_and_saves(pg):
    names = pg.eval_on_selector_all('#game option', 'o => o.map(x => x.textContent)')
    assert names == ['Klondike', 'FreeCell', 'Golf', 'Pyramid', 'Spider', 'Forty Thieves', 'Yukon', 'TriPeaks'], names
    start(pg, 'klondike')
    box = pg.locator('.slot[data-pile=stock]').bounding_box()
    pg.mouse.click(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
    pg.wait_for_timeout(300)
    klondike = status(pg)
    assert 'Moves 1' in klondike, klondike
    open_game(pg, 'freecell')
    open_game(pg, 'klondike')
    assert status(pg) == klondike, 'switching games must not lose the game left behind'
    pg.reload()
    pg.wait_for_timeout(700)
    assert status(pg) == klondike, 'a reload must restore the saved game'


def check_shift_highlight(pg):
    start(pg, 'freecell')
    assert count(pg, 'hint') == 0 and count(pg, 'dim') == 0
    shift(pg, True)
    assert count(pg, 'hint') > 0 and count(pg, 'dim') > 0
    assert count(pg, 'hint') + count(pg, 'dim') == pg.locator('.card').count(), 'every card is lit or dimmed'
    # Performance guard: a CSS filter, or a transition on one, forces every card's SVG to be re-rendered.
    style = pg.evaluate("""() => { const c = document.querySelector('.card.dim');
        return { filter: getComputedStyle(c).filter, transition: getComputedStyle(c).transitionProperty,
                 overlay: getComputedStyle(c, '::after').content } }""")
    assert style['filter'] == 'none', style
    assert 'filter' not in style['transition'] and 'all' not in style['transition'], style
    assert style['overlay'] != 'none', 'dimming should be an overlay'
    shift(pg, False)
    assert count(pg, 'hint') == 0 and count(pg, 'dim') == 0, 'releasing Shift clears everything'


def check_rank_keys(pg):
    start(pg, 'freecell')
    pg.keyboard.down('1')
    pg.wait_for_timeout(120)
    assert lit(pg) == ['Ace of clubs', 'Ace of diamonds', 'Ace of hearts', 'Ace of spades'], 'a rank key lights every ace'
    pg.keyboard.down('Shift')
    pg.wait_for_timeout(120)
    both = lit(pg)
    assert len(both) == 3 and all(l.startswith('Ace') for l in both), f'adding Shift keeps only the movable aces: {both}'
    pg.keyboard.up('Shift')
    pg.keyboard.up('1')
    pg.wait_for_timeout(120)
    assert count(pg, 'hint') == 0

    start(pg, 'klondike')
    for key in 'a23456789jqk0t':
        pg.keyboard.down(key)
        pg.wait_for_timeout(40)
        assert FACE_DOWN not in lit(pg), f'key {key} lit a face-down card'
        pg.keyboard.up(key)

    pg.focus('#game')
    pg.keyboard.press('k')
    assert count(pg, 'hint') == 0, 'rank keys are ignored while the menu has focus'
    pg.evaluate('document.activeElement.blur()')


def check_toggle_persists(pg):
    start(pg, 'golf')
    pg.click('#hints')
    assert pg.get_attribute('#hints', 'aria-pressed') == 'true' and count(pg, 'hint') > 0
    pg.reload()
    pg.wait_for_timeout(700)
    assert pg.get_attribute('#hints', 'aria-pressed') == 'true' and count(pg, 'hint') > 0, 'Show moves is remembered'
    pg.click('#hints')
    assert count(pg, 'hint') == 0 and count(pg, 'dim') == 0


def check_golf_tap_and_undo(pg):
    start(pg, 'golf')
    before = status(pg)
    shift(pg, True)
    labels = [l for l in lit(pg) if l != FACE_DOWN]
    assert labels, 'a Golf deal should offer a playable card'
    box = pg.locator(f'.card[aria-label="{labels[0]}"]').bounding_box()
    shift(pg, False)
    pg.mouse.click(box['x'] + box['width'] / 2, box['y'] + box['height'] * 0.2)
    pg.wait_for_timeout(300)
    assert status(pg) != before and 'Moves 1' in status(pg), status(pg)
    pg.click('#undo')
    pg.wait_for_timeout(200)
    assert status(pg) == before, 'undo restores the position'


def check_tap_moves_are_animated_even_with_reduced_motion(pg):
    """A short slide stays when the device asks for reduced motion: iPads often do, and it is feedback."""
    context = pg.context.browser.new_context(viewport={'width': 1000, 'height': 900}, reduced_motion='reduce')
    context.route('**/fonts.googleapis.com/**', lambda route: route.abort())
    page = context.new_page()
    page.goto(URL)
    page.wait_for_timeout(700)
    check_tap_moves_are_animated(page)
    context.close()


def check_animation_survives_a_small_resize(pg):
    """A wobble of a few dozen pixels in the height (as a standalone iPad app reports) must not switch animation off."""
    pg.set_viewport_size({'width': 1000, 'height': 850})
    pg.wait_for_timeout(300)
    check_tap_moves_are_animated(pg)


def check_diagnostics_panel(pg):
    assert pg.locator('#diagnostics').is_hidden()
    for _ in range(5):
        pg.click('h1')
    assert pg.locator('#diagnostics').is_visible()
    text = pg.locator('#diagnostics').inner_text()
    assert 'inner 1000x900' in text and 'relayouts' in text, text
    for _ in range(5):
        pg.click('h1')
    assert pg.locator('#diagnostics').is_hidden()


def check_tap_moves_are_animated(pg):
    """A tapped card glides to its place, above the other cards, rather than jumping."""
    start(pg, 'golf')
    shift(pg, True)
    label = [l for l in lit(pg) if l != FACE_DOWN][0]
    box = pg.locator(f'.card[aria-label="{label}"]').bounding_box()
    shift(pg, False)
    pg.evaluate("""label => { const el = document.querySelector(`.card[aria-label="${label}"]`);
        window.__track = []; const t0 = performance.now();
        const sample = () => { const m = new DOMMatrix(getComputedStyle(el).transform);
            window.__track.push({ t: performance.now() - t0, x: m.m41, y: m.m42, z: +getComputedStyle(el).zIndex });
            if (performance.now() - t0 < 600) requestAnimationFrame(sample); };
        sample(); }""", label)
    pg.mouse.click(box['x'] + box['width'] / 2, box['y'] + box['height'] * 0.2)
    pg.wait_for_timeout(700)
    track = pg.evaluate("window.__track")
    far = lambda s, t: abs(s['x'] - t['x']) + abs(s['y'] - t['y']) > 8        # the last pixels of an ease-out do not count
    moving = [s for s in track if far(s, track[0]) and far(s, track[-1])]
    assert len(moving) >= 3, f'the card should be seen part-way along its path: {len(moving)} samples'
    assert all(s['z'] >= 60000 for s in moving), ('it flies above the other cards', [s for s in moving if s['z'] < 60000][:3], track[:3])
    assert track[-1]['z'] < 60000, f'and settles into the stack: {track[-1]}'


def check_freecell_drag_and_double_tap(pg):
    start(pg, 'freecell')
    cards = pg.evaluate("""() => [...document.querySelectorAll('.card')].map(c => {
        const m = c.style.transform.match(/translate\\(([-\\d.]+)px, ([-\\d.]+)px\\)/);
        return { id: c.dataset.id, x: +m[1], y: +m[2], z: +c.style.zIndex } })""")
    columns = sorted({round(c['x']) for c in cards if c['y'] > 50})
    def last_of(x):
        return sorted([c for c in cards if abs(c['x'] - x) < 2 and c['y'] > 50], key=lambda c: c['z'])[-1]['id']
    centre = lambda sel: (lambda b: (b['x'] + b['width'] / 2, b['y'] + b['height'] / 2))(pg.locator(sel).bounding_box())
    (sx, sy), (tx, ty) = centre(f'.card[data-id="{last_of(columns[0])}"]'), centre('.slot[data-pile=c0]')
    pg.mouse.move(sx, sy)
    pg.mouse.down()
    pg.mouse.move(tx, ty, steps=8)
    pg.mouse.up()
    pg.wait_for_timeout(300)
    assert 'Free cells 3 / 4' in status(pg), status(pg)
    cx, cy = centre(f'.card[data-id="{last_of(columns[1])}"]')
    pg.mouse.dblclick(cx, cy)
    pg.wait_for_timeout(300)
    assert 'Moves 2' in status(pg), status(pg)


def check_rules_card(pg):
    start(pg, 'klondike')
    assert pg.locator('.notes').count() == 0, 'the old bottom notes are gone'
    assert not pg.is_visible('#rules')
    pg.click('#rules-btn')
    assert pg.is_visible('#rules') and pg.get_attribute('#rules-btn', 'aria-expanded') == 'true'
    assert pg.inner_text('#rules-title') == 'Klondike' and 'foundations' in pg.inner_text('#rules-text')
    assert pg.evaluate("document.activeElement.id") == 'rules-close', 'focus moves into the card'
    # nothing from the table may paint over the card: sample points across it
    covered = pg.evaluate("""() => { const r = document.getElementById('rules').getBoundingClientRect(); const bad = [];
        for (const fx of [0.1, 0.3, 0.5, 0.7, 0.9]) for (const fy of [0.1, 0.3, 0.5, 0.7, 0.9]) {
          const el = document.elementFromPoint(r.left + r.width * fx, r.top + Math.min(r.height, 500) * fy);
          if (!el || !el.closest('#rules')) bad.push([fx, fy, el && (el.className || el.tagName)]); }
        return bad }""")
    assert not covered, f'something paints over the rules card: {covered}'
    # rank keys must not light cards behind the open card
    pg.keyboard.down('a')
    pg.wait_for_timeout(100)
    assert count(pg, 'hint') == 0, 'rank keys are ignored while the rules are open'
    pg.keyboard.up('a')
    # the card is fully inside the viewport and does not overflow the page
    box = pg.locator('#rules').bounding_box()
    assert box['x'] >= 0 and box['x'] + box['width'] <= 1000, box
    # Escape closes it and returns focus to the button
    pg.keyboard.press('Escape')
    assert not pg.is_visible('#rules') and pg.evaluate("document.activeElement.id") == 'rules-btn'
    # the close button works
    pg.click('#rules-btn')
    pg.click('#rules-close')
    assert not pg.is_visible('#rules')
    # a click outside closes it
    pg.click('#rules-btn')
    pg.mouse.click(900, 700)
    assert not pg.is_visible('#rules'), 'clicking elsewhere closes the card'
    # it follows the game while open
    pg.click('#rules-btn')
    pg.select_option('#game', GAMES['golf'])
    pg.wait_for_timeout(500)
    assert pg.inner_text('#rules-title') == 'Golf' and 'column' in pg.inner_text('#rules-text')
    # on a phone it stays inside the screen
    pg.set_viewport_size({'width': 400, 'height': 760})
    pg.wait_for_timeout(300)
    box = pg.locator('#rules').bounding_box()
    assert box['x'] >= 0 and box['x'] + box['width'] <= 400, box
    assert not pg.evaluate('document.documentElement.scrollWidth > innerWidth'), 'no sideways scroll'


def check_pyramid(pg):
    start(pg, 'pyramid')
    assert 'Left 28 / 28' in status(pg), status(pg)
    assert pg.locator('.slot').count() == 3, 'the stock, waste and removed pile have outlines'
    shift(pg, True)
    assert lit(pg) == sorted([FACE_DOWN, 'Ace of spades', 'King of hearts', 'Queen of spades']), lit(pg)
    shift(pg, False)

    def tap_label(label):
        tap(pg, f'.card[aria-label="{label}"]', wait=250)

    tap_label('Queen of spades')
    assert pg.locator('.card.selected').count() == 1, 'the first card of a pair is selected'
    tap_label('Ace of spades')
    assert 'Left 26 / 28' in status(pg) and 'Moves 1' in status(pg), status(pg)
    pg.wait_for_timeout(300)
    out = pg.locator('.slot[data-pile=out]').bounding_box()
    gone = pg.locator('.card[aria-label="Ace of spades"]').bounding_box()
    assert abs(gone['x'] - out['x']) < 3 and abs(gone['y'] - out['y']) < 3, 'removed cards go to the removed pile'
    tap_label('King of hearts')
    assert 'Left 25 / 28' in status(pg), status(pg)
    pg.click('#undo')
    pg.click('#undo')
    pg.wait_for_timeout(300)
    assert 'Left 28 / 28' in status(pg) and 'Moves 0' in status(pg), status(pg)
    # two cards that do not add up to 13 only move the selection
    cards = pg.evaluate("""() => [...document.querySelectorAll('.card')].map(c => ({
        label: c.getAttribute('aria-label'), y: c.getBoundingClientRect().y }))""")
    free_row = max(c['y'] for c in cards if c['label'] != FACE_DOWN)
    bottom = [c['label'] for c in cards if abs(c['y'] - free_row) < 3 and c['label'] not in
              ('Queen of spades', 'Ace of spades', 'King of hearts')][:2]
    assert len(bottom) == 2, bottom
    tap_label(bottom[0])
    tap_label(bottom[1])
    assert 'Moves 0' in status(pg) and pg.locator('.card.selected').count() == 1, status(pg)
    # the stock draws
    box = pg.locator('.slot[data-pile=stock]').bounding_box()
    pg.mouse.click(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
    pg.wait_for_timeout(250)
    assert 'Stock 23' in status(pg) and 'Moves 1' in status(pg), status(pg)
    assert pg.locator('.card.selected').count() == 0, 'drawing clears the selection'


STACKING_PROBLEMS = """() => {
    const cards = [...document.querySelectorAll('.card')].map(c => {
        const r = c.getBoundingClientRect();
        return { label: c.getAttribute('aria-label'), x: r.x, y: r.y, w: r.width, h: r.height,
                 z: +c.style.zIndex, order: [...c.parentNode.children].indexOf(c) };
    });
    const bad = [];
    for (const a of cards) for (const b of cards) {
        const overlap = Math.min(a.x + a.w, b.x + b.w) > Math.max(a.x, b.x) + 2 &&
                        Math.min(a.y + a.h, b.y + b.h) > Math.max(a.y, b.y) + 2;
        if (!overlap || b.y - a.y < 5) continue;          // b is the lower card and must paint above a
        const above = b.z > a.z || (b.z === a.z && b.order > a.order);
        if (!above) bad.push([a.label, b.label]);
    }
    return bad;
}"""


def check_pyramid_stacking(pg):
    start(pg, 'pyramid')
    assert not pg.evaluate(STACKING_PROBLEMS), 'fresh deal'
    # A new deal reuses the card elements, so stacking must not depend on their order in the page.
    for n in range(3):
        pg.click('#new')
        wait_for_deal(pg)
        problems = pg.evaluate(STACKING_PROBLEMS)
        assert not problems, f'after new deal {n + 1}: {problems[:3]}'
    # Undo re-creates cards that were taken off the table.
    pg.evaluate("""() => localStorage.setItem('baize.v2', JSON.stringify({ current: 'pyramid', games: { pyramid: {
        options: {}, seed: 1, actions: [{ type: 'take', from: ['p6_2'] }, { type: 'take', from: ['p6_3', 'p6_4'] },
                                        { type: 'take', from: ['p5_3', 'p6_6'] }] } } }))""")
    pg.reload()
    pg.wait_for_timeout(800)
    for step in range(3):
        pg.click('#undo')
        pg.wait_for_timeout(300)
        problems = pg.evaluate(STACKING_PROBLEMS)
        assert not problems, f'after undo {step + 1}: {problems[:3]}'


def check_stacking_every_game(pg):
    for name in GAMES:
        start(pg, name)
        wait_for_deal(pg)
        problems = pg.evaluate(STACKING_PROBLEMS)
        assert not problems, f'{name}: {problems[:3]}'


def check_spider(pg):
    start(pg, 'spider')
    assert 'Runs 0 / 8' in status(pg) and 'Deals left 5' in status(pg), status(pg)
    assert pg.locator('.card').count() == 104, 'two decks are on the table'
    shift(pg, True)
    assert pg.locator('.card.hint').count() > 0, 'some card can move'
    shift(pg, False)

    def tap_card(card_id, where=0.2):
        tap(pg, f'.card[data-id="{card_id}"]', where)

    tap_card('s6.2')
    assert pg.locator('.card.selected').count() == 1, 'the first tap selects'
    tap_card('s7.2')
    assert 'Moves 1' in status(pg), status(pg)
    pg.click('#undo')
    pg.wait_for_timeout(300)
    box = pg.locator('.slot[data-pile="stock"]').bounding_box()
    pg.mouse.click(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
    pg.wait_for_timeout(500)
    assert 'Deals left 4' in status(pg) and 'Moves 1' in status(pg), status(pg)
    problems = pg.evaluate(STACKING_PROBLEMS)
    assert not problems, problems[:3]


def check_yukon(pg):
    start(pg, 'yukon')
    assert 'Home 0 / 52' in status(pg) and 'Hidden 21' in status(pg), status(pg)
    assert pg.locator('.card').count() == 52
    # find a move that carries several cards
    move = pg.evaluate("""() => {
        const rules = CardSim.yukon, state = rules.setup({}, CardSim.mulberry32(3));
        for (const [from, es] of Object.entries(state.piles)) for (let index = 0; index < es.length - 1; index++)
            for (const to of Object.keys(state.piles)) {
                const m = { type: 'move', from, index, to };
                if (to.startsWith('t') && rules.reduce(state, m, {}).state) {
                    return { ...m, lead: es[index].card.id, landing: state.piles[to].at(-1)?.card.id, size: es.length - index };
                }
            }
        return null; }""")
    assert move and move['size'] > 1 and move['landing'], move

    def tap_card(card_id, where=0.2):
        tap(pg, f'.card[data-id="{card_id}"]', where)

    tap_card(move['lead'])
    assert pg.locator('.card.selected').count() == move['size'], 'the whole stack is selected'
    tap_card(move['landing'], 0.5)
    assert 'Moves 1' in status(pg), status(pg)
    pg.click('#undo')
    pg.wait_for_timeout(300)
    assert 'Moves 0' in status(pg)
    problems = pg.evaluate(STACKING_PROBLEMS)
    assert not problems, problems[:3]


def check_tripeaks(pg):
    start(pg, 'tripeaks')
    assert 'Left 28 / 28' in status(pg) and 'Stock 23' in status(pg), status(pg)
    assert pg.locator('.card').count() == 52
    hidden = pg.evaluate("l => [...document.querySelectorAll('.card')].filter(c => c.getAttribute('aria-label') === l).length", FACE_DOWN)
    assert hidden == 18 + 23, f'only the base row and the waste show: {hidden} face down'
    play = pg.evaluate("""() => {
        const rules = CardSim.tripeaks, state = rules.setup({ wrap: 0 }, CardSim.mulberry32(5));
        const showing = state.piles.waste.at(-1).card.rank;
        return rules.moves(state, { wrap: 0 }).filter(a => a.type === 'play')
            .map(a => ({ pile: a.from, id: state.piles[a.from][0].card.id }))[0] ?? null; }""")
    assert play, 'seed 5 offers a first play'
    b = pg.locator(f'.card[data-id="{play["id"]}"]').bounding_box()
    pg.mouse.click(b['x'] + b['width'] / 2, b['y'] + b['height'] * 0.2)
    pg.wait_for_timeout(400)
    assert 'Left 27 / 28' in status(pg) and 'Moves 1' in status(pg), status(pg)
    pg.click('#undo')
    pg.wait_for_timeout(300)
    assert 'Left 28 / 28' in status(pg)
    box = pg.locator('.slot[data-pile="stock"]').bounding_box()
    pg.mouse.click(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
    pg.wait_for_timeout(400)
    assert 'Stock 22' in status(pg), status(pg)
    problems = pg.evaluate(STACKING_PROBLEMS)
    assert not problems, problems[:3]


def check_forty_thieves(pg):
    start(pg, 'forty')
    assert 'Home 0 / 104' in status(pg) and 'Stock 64' in status(pg), status(pg)
    assert pg.locator('.card').count() == 104

    def tap_card(card_id, where=0.2):
        tap(pg, f'.card[data-id="{card_id}"]', where)

    tap_card('h2.1')
    tap_card('h3.1')
    assert 'Moves 1' in status(pg), status(pg)
    pg.click('#undo')
    pg.wait_for_timeout(300)
    box = pg.locator('.slot[data-pile="stock"]').bounding_box()
    pg.mouse.click(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
    pg.wait_for_timeout(500)
    assert 'Stock 63' in status(pg) and 'Moves 1' in status(pg), status(pg)
    problems = pg.evaluate(STACKING_PROBLEMS)
    assert not problems, problems[:3]


def check_redeal_order(pg):
    """A new deal picks the cards up top first, clears the whole table, and only then deals."""
    for name in ('klondike', 'pyramid'):
        start(pg, name)
        pg.wait_for_timeout(300)
        before = pg.evaluate("""() => Object.fromEntries([...document.querySelectorAll('.card')].map(
            c => [c.dataset.id, { z: +c.style.zIndex, at: c.style.transform }]))""")
        pg.evaluate("""() => {
            window.__departures = [];
            const stock = document.querySelector('.slot[data-pile="stock"]');
            window.__anchor = stock.style.transform;
            window.__t0 = performance.now();
            new MutationObserver(() => {
                const moved = [...document.querySelectorAll('.card')].some(c => c.style.transform !== window.__anchor);
                if (moved) window.__departures.push(performance.now() - window.__t0);
            }).observe(document.getElementById('board'), { subtree: true, attributes: true, attributeFilter: ['style'] });
        }""")
        pg.click('#new')
        gathering = pg.evaluate("""() => [...document.querySelectorAll('.card')].map(c => (
            { id: c.dataset.id, delay: parseFloat(c.style.transitionDelay) || 0, at: c.style.transform }))""")
        anchor = pg.evaluate('window.__anchor')
        moving = sorted((c for c in gathering if before[c['id']]['at'] != anchor), key=lambda c: c['delay'])
        assert moving and all(c['at'] == anchor for c in moving), f'{name}: every card heads for the deck'
        zs = [before[c['id']]['z'] for c in moving]
        assert zs == sorted(zs, reverse=True), f'{name}: cards are picked up from the top of the stacking order down'
        wait_for_deal(pg)
        assert not pg.evaluate(STACKING_PROBLEMS), f'{name}: stacking after the redeal'
        gather_ms = moving[-1]['delay'] + 220
        # Every card has left in the gather phase; the first move away from the deck after that is the deal.
        later = pg.evaluate('window.__departures')
        assert later, f'{name}: the new deal was laid out'
        assert later[0] >= gather_ms, f'{name}: dealing began at {later[0]:.0f} ms, before the table was clear ({gather_ms:.0f} ms)'
        assert pg.evaluate("document.querySelectorAll('.card').length") == len(before)


def choose(pg, option, value):
    """Pick an option the way a person does: open the menu, then press the button."""
    pg.click('#options-btn')
    pg.click(f'button[data-option="{option}"][data-value="{value}"]')


def check_winnable_deals(pg):
    start(pg, 'freecell')
    choose(pg, 'winnable', 1)
    wait_for_deal(pg)
    stored = pg.evaluate("JSON.parse(localStorage.getItem('baize.v2')).games.freecell")
    assert stored['options']['winnable'] == 1, stored
    assert 'No winnable' not in status(pg), status(pg)
    solved = pg.evaluate("""({ seed, options }) => {
        const rules = CardSim.freecell;
        return Boolean(CardSim.solve(rules, options, rules.setup(options, CardSim.mulberry32(seed)), { nodes: 3000 }));
    }""", stored)
    assert solved, 'the dealt game can be won'
    pg.click('#new')
    wait_for_deal(pg)
    again = pg.evaluate("JSON.parse(localStorage.getItem('baize.v2')).games.freecell")
    assert again['seed'] != stored['seed'] and again['options']['winnable'] == 1, 'New deal keeps the setting and picks another'
    pg.evaluate('window.Worker = undefined')            # where workers are blocked the search runs on the page
    pg.click('#new')
    wait_for_deal(pg)
    last = pg.evaluate("JSON.parse(localStorage.getItem('baize.v2')).games.freecell")
    assert last['seed'] != again['seed'] and 'No winnable' not in status(pg), status(pg)
    assert pg.evaluate("""({ seed, options }) => Boolean(CardSim.solve(CardSim.freecell, options,
        CardSim.freecell.setup(options, CardSim.mulberry32(seed)), { nodes: 3000 }))""", last), 'fallback deal can be won'
    # Spider can only promise winnable deals with one suit, so the setting is not offered otherwise.
    start(pg, 'spider')
    pg.click('#options-btn')
    assert pg.locator('[data-option-group="winnable"]').is_visible()
    pg.click('button[data-option="suits"][data-value="2"]')
    wait_for_deal(pg)
    assert not pg.locator('#options').is_visible(), 'choosing an option closes the menu'
    pg.click('#options-btn')
    assert not pg.locator('[data-option-group="winnable"]').is_visible()
    pg.keyboard.press('Escape')
    assert not pg.locator('#options').is_visible(), 'Escape closes the menu'
    assert pg.evaluate("document.activeElement.id") == 'options-btn'
    pg.click('#options-btn')
    pg.mouse.click(5, 5)
    assert not pg.locator('#options').is_visible(), 'clicking elsewhere closes the menu'
    pg.click('#options-btn')
    pg.click('#rules-btn')
    assert not pg.locator('#options').is_visible() and pg.locator('#rules').is_visible(), 'only one popover at a time'


VIEWPORTS = {'phone': (390, 844, True), 'phone landscape': (844, 390, True), 'tablet': (820, 1180, True),
             'tablet landscape': (1180, 820, True), 'desktop': (1280, 800, False)}


def check_responsive(pg):
    """Every game fits every screen: nothing hangs over the table or the page edge, buttons are
    finger-sized on touch screens, and the options menu fits."""
    browser = pg.context.browser
    for label, (w, h, touch) in VIEWPORTS.items():
        context = browser.new_context(viewport={'width': w, 'height': h}, has_touch=touch, is_mobile=touch)
        context.route('**/fonts.googleapis.com/**', lambda route: route.abort())     # keep the run offline-fast
        page = context.new_page()
        page.goto(URL)
        for name in GAMES:
            start(page, name)
            fit = page.evaluate("""() => {
                const board = document.getElementById('board').getBoundingClientRect();
                const out = [...document.querySelectorAll('.card')].map(c => c.getBoundingClientRect())
                    .filter(r => r.left < board.left - 1 || r.right > board.right + 1);
                const root = document.documentElement;
                return { outside: out.length, overflowX: root.scrollWidth - root.clientWidth,
                         bottom: board.bottom, height: innerHeight };
            }""")
            assert fit['outside'] == 0, f'{label} {name}: {fit["outside"]} cards stick out of the table'
            assert fit['overflowX'] <= 0, f'{label} {name}: the page scrolls sideways'
            assert fit['bottom'] <= fit['height'] + 2, f'{label} {name}: the table runs off the bottom ({fit})'
            lock = page.evaluate("""() => { const r = document.documentElement;
                return { scrollbar: innerWidth - r.clientWidth, overflowY: r.scrollHeight - r.clientHeight,
                         overflow: getComputedStyle(r).overflow, body: getComputedStyle(document.body).overflow }; }""")
            assert lock['scrollbar'] == 0 and lock['overflowY'] <= 0 and lock['overflow'] == 'hidden' == lock['body'], f'{label} {name}: the page can scroll {lock}'
        if touch:
            small = page.evaluate("""() => [...document.querySelectorAll('.bar button, .bar select')]
                .filter(b => b.offsetParent !== null && b.getBoundingClientRect().height < 43).map(b => b.id || b.textContent)""")
            assert not small, f'{label}: buttons under 44 px: {small}'
        start(page, 'klondike')
        assert not page.locator('#options').is_visible(), f'{label}: options start closed'
        page.click('#options-btn')
        menu = page.evaluate("""() => { const r = document.getElementById('options').getBoundingClientRect();
            return { left: r.left, right: r.right, bottom: r.bottom, w: innerWidth, h: innerHeight }; }""")
        assert menu['left'] >= 0 and menu['right'] <= menu['w'] and menu['bottom'] <= menu['h'], f'{label}: the menu fits the screen {menu}'
        near = page.evaluate("""() => { const m = document.getElementById('options').getBoundingClientRect(), b = document.getElementById('options-btn').getBoundingClientRect();
            return { gap: m.top - b.bottom, overlap: Math.min(m.right, b.right) - Math.max(m.left, b.left) }; }""")
        assert 0 <= near['gap'] <= 16 and near['overlap'] > 0, f'{label}: the menu hangs from its button {near}'
        body = page.evaluate("(() => { const r = document.body.getBoundingClientRect(); return [r.left, r.top, r.width, r.height, innerWidth, innerHeight]; })()")
        assert body[:2] == [0, 0] and body[2:4] == body[4:], f'{label}: the page fills the screen exactly {body}'
        context.close()


def check_search_can_be_cancelled(pg):
    start(pg, 'freecell')
    choose(pg, 'winnable', 1)
    wait_for_deal(pg)
    # A worker that never answers stands in for a search that takes a long time.
    pg.evaluate("() => { window.Worker = class { postMessage() {} terminate() {} }; }")
    pg.click('#new')
    assert pg.locator('#busy').is_hidden(), 'a search that has only just begun shows nothing'
    pg.wait_for_timeout(600)
    assert pg.locator('#busy').is_visible() and 'winnable' in pg.locator('#busy-title').inner_text().lower()
    assert pg.locator('#busy-spinner').is_visible() and pg.locator('#busy-btn').inner_text() == 'Cancel'
    over = pg.evaluate("""() => { const r = document.getElementById('busy').getBoundingClientRect(), t = document.getElementById('table').getBoundingClientRect();
        return r.left == t.left && r.right == t.right && r.top == t.top && r.bottom == t.bottom; }""")
    assert over, 'the dialogue covers the play area'
    pg.click('#busy-btn')
    wait_for_deal(pg)
    assert pg.locator('#busy').is_hidden(), 'Cancel closes the dialogue'
    assert pg.locator('.card').count() == 52, 'a deal was made all the same'
    # Escape cancels too
    pg.click('#new')
    pg.wait_for_timeout(600)
    pg.keyboard.press('Escape')
    wait_for_deal(pg)
    assert pg.locator('#busy').is_hidden()
    # A search that runs out of time says so, and OK dismisses it.
    pg.evaluate("() => { window.Worker = class { postMessage() { setTimeout(() => this.onmessage({ data: { seed: null } }), 600); } terminate() {} }; }")
    pg.click('#new')
    wait_for_deal(pg)
    assert pg.locator('#busy').is_visible() and pg.locator('#busy-btn').inner_text() == 'OK'
    assert pg.locator('#busy-spinner').is_hidden(), 'no spinner once it has finished'
    pg.click('#busy-btn')
    assert pg.locator('#busy').is_hidden()


def check_page_cannot_zoom(pg):
    assert pg.evaluate("document.querySelector('meta[name=viewport]').content") .count('user-scalable=no') == 1
    # the rules card still scrolls on its own
    pg.click('#rules-btn')
    assert pg.evaluate("getComputedStyle(document.querySelector('.rules-scroll')).overflowY") == 'auto'
    assert pg.evaluate("getComputedStyle(document.querySelector('.rules-scroll')).touchAction") == 'pan-y'
    assert pg.evaluate("getComputedStyle(document.body).touchAction") == 'none'
    # Ctrl and the wheel, and a double-click, are not allowed to zoom
    prevented = pg.evaluate("""() => [new WheelEvent('wheel', { ctrlKey: true, cancelable: true, bubbles: true }),
        new Event('gesturestart', { cancelable: true, bubbles: true })].map(e => { document.body.dispatchEvent(e); return e.defaultPrevented; })""")
    assert prevented == [True, True], prevented


def check_selected_and_highlighted_combine(pg):
    """A selected card tilts and lifts; Show moves draws a ring; a card can be both."""
    start(pg, 'freecell')
    pg.click('#hints')
    label = [l for l in lit(pg) if l != FACE_DOWN][0]
    card = pg.locator(f'.card[aria-label="{label}"]')
    box = card.bounding_box()
    pg.mouse.click(box['x'] + box['width'] / 2, box['y'] + box['height'] * 0.9)
    pg.wait_for_timeout(400)
    style = card.evaluate("""el => { const c = getComputedStyle(el); const m = new DOMMatrix(c.transform);
        return { angle: Math.atan2(m.b, m.a) * 180 / Math.PI, shadow: c.boxShadow, cls: el.className }; }""")
    assert 'selected' in style['cls'] and 'hint' in style['cls'], style
    assert abs(style['angle'] - 6) < 0.5, style
    after = card.bounding_box()
    centre = lambda b: (b['x'] + b['width'] / 2, b['y'] + b['height'] / 2)
    assert abs(centre(after)[0] - centre(box)[0]) < 1.5 and abs(centre(after)[1] - centre(box)[1]) < 1.5, \
        f'the card tilts about its own centre: {centre(box)} -> {centre(after)}'
    assert style['shadow'].count('rgb') >= 3, f'the ring and the lift both show: {style}'


def check_winnable_preference_is_shared(pg):
    start(pg, 'freecell')
    choose(pg, 'winnable', 1)
    wait_for_deal(pg)
    for name in ('klondike', 'golf', 'pyramid'):
        open_game(pg, name)
        pressed = pg.evaluate("document.querySelector('button[data-option=winnable][aria-pressed=true]')?.dataset.value")
        assert pressed == '1', f'{name} keeps Winnable'
    choose(pg, 'winnable', 0)
    wait_for_deal(pg)
    open_game(pg, 'freecell')
    assert pg.evaluate("document.querySelector('button[data-option=winnable][aria-pressed=true]').dataset.value") == '0'


def check_rules_text_stays_inside_the_frame(pg):
    """However far the rules are scrolled, the text (the credit line included) sits inside the gold frame."""
    pg.set_viewport_size({'width': 420, 'height': 560})
    pg.wait_for_timeout(300)
    pg.click('#rules-btn')
    for position in (0, 1):
        pg.evaluate("p => { const s = document.querySelector('.rules-scroll'); s.scrollTop = p * s.scrollHeight; }", position)
        pg.wait_for_timeout(100)
        box = pg.evaluate("""() => { const r = document.getElementById('rules').getBoundingClientRect();
            const inside = [...document.querySelectorAll('.rules-scroll > *')].map(e => e.getBoundingClientRect())
                .filter(b => b.bottom > r.top && b.top < r.bottom);              // what is on show
            const s = document.querySelector('.rules-scroll').getBoundingClientRect();
            return { frameTop: r.top + 7, frameBottom: r.bottom - 7, frameLeft: r.left + 7, frameRight: r.right - 7,
                     scroller: [s.top, s.bottom, s.left, s.right],
                     scrolls: document.querySelector('.rules-scroll').scrollHeight > document.querySelector('.rules-scroll').clientHeight }; }""")
        assert box['scrolls'], 'the rules are long enough to scroll on this screen'
        s_top, s_bottom, s_left, s_right = box['scroller']
        assert s_top >= box['frameTop'] and s_bottom <= box['frameBottom'] and s_left >= box['frameLeft'] and s_right <= box['frameRight'], \
            f'the scrolling text stays within the frame: {box}'
    assert pg.evaluate("document.getElementById('rules').scrollHeight <= document.getElementById('rules').clientHeight + 1"), 'the frame itself does not scroll'


def stats_rows(pg):
    pg.click('#options-btn')
    pg.click('#stats-btn')
    rows = pg.evaluate("[...document.querySelectorAll('#stats-table tr')].map(r => [...r.children].map(c => c.textContent))")
    return {r[0]: r[1:] for r in rows}


def check_statistics(pg):
    assert stats_rows(pg)['Golf'] == ['–'] * 5, 'nothing played yet'
    pg.keyboard.press('Escape')
    assert pg.locator('#stats').is_hidden(), 'Escape closes the panel'
    assert pg.evaluate("document.activeElement.id") == 'options-btn'
    # A saved, already-won Golf deal: load it and the win is counted, once.
    saved = pg.evaluate("""() => {
        const options = { wrap: 1, winnable: 0 }, rules = CardSim.golf;
        for (let seed = 0; seed < 200; seed++) {
            const actions = CardSim.solve(rules, options, rules.setup(options, CardSim.mulberry32(seed)), { nodes: 3000 });
            if (actions) return { seed, options, actions };
        }
        return null; }""")
    assert saved
    pg.evaluate("""s => localStorage.setItem('baize.v2', JSON.stringify({ current: 'golf', games: { golf: s } }))""", saved)
    pg.reload()
    pg.wait_for_timeout(700)
    golf = stats_rows(pg)['Golf']
    moves = str(len(saved['actions']))
    assert golf == ['1', '1', '100%', moves, '1 (1)'], golf
    pg.keyboard.press('Escape')
    pg.reload()
    pg.wait_for_timeout(700)
    assert stats_rows(pg)['Golf'] == golf, 'reloading a won deal does not count it again'
    pg.keyboard.press('Escape')
    # undo and win again: still one
    pg.click('#undo')
    pg.wait_for_timeout(300)
    pg.click('#new')                                  # given up after a win that was undone: not counted either
    wait_for_deal(pg)
    assert stats_rows(pg)['Golf'] == golf, stats_rows(pg)['Golf']
    pg.keyboard.press('Escape')
    # a deal given up after a move counts as played and ends the streak
    box = pg.locator('.slot[data-pile="stock"]').bounding_box()
    pg.mouse.click(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
    pg.wait_for_timeout(300)
    pg.click('#new')
    wait_for_deal(pg)
    assert stats_rows(pg)['Golf'] == ['2', '1', '50%', moves, '0 (1)'], stats_rows(pg)['Golf']
    # a deal with no moves, or a restart, is not counted
    pg.keyboard.press('Escape')
    pg.click('#new')
    wait_for_deal(pg)
    assert stats_rows(pg)['Golf'][0] == '2'
    # reset needs two presses
    pg.click('#stats-reset')
    assert stats_rows(pg)['Golf'][0] == '2', 'one press only arms the reset'
    pg.click('#stats-reset')
    pg.click('#stats-reset')
    assert pg.evaluate("[...document.querySelectorAll('#stats-table tr')].map(r => r.children[1].textContent).slice(1).every(t => t === '–')")


def check_hint(pg):
    """Hint lights the first move of a winning line, which really is playable and really wins."""
    saved = pg.evaluate("""() => {
        const options = { wrap: 1, winnable: 0 }, rules = CardSim.golf;
        for (let seed = 0; seed < 200; seed++) {
            const actions = CardSim.solve(rules, options, rules.setup(options, CardSim.mulberry32(seed)), { nodes: 3000 });
            if (actions) return { seed, options, actions };
        }
        return null; }""")
    pg.evaluate("""s => localStorage.setItem('baize.v2', JSON.stringify({ current: 'golf', games: { golf: { seed: s.seed, options: s.options, actions: [] } } }))""", saved)
    pg.reload()
    pg.wait_for_timeout(700)
    assert pg.locator('.card.suggest').count() == 0
    pg.click('#options-btn')
    pg.click('#hint-btn')
    pg.wait_for_selector('.card.suggest, .slot.suggest-to', timeout=20000)
    assert 'win is still possible' in pg.locator('#toast').inner_text(), pg.locator('#toast').inner_text()
    pg.wait_for_timeout(6500)
    assert pg.locator('#toast').is_visible(), 'the message stays until the player acts'
    first = saved['actions'][0]
    if first['type'] == 'play':
        lit_ids = pg.evaluate("[...document.querySelectorAll('.card.suggest')].map(c => c.dataset.id)")
        assert len(lit_ids) == 1, lit_ids
        b = pg.locator('.card.suggest').bounding_box()
        pg.mouse.click(b['x'] + b['width'] / 2, b['y'] + b['height'] * 0.2)
    else:
        assert pg.locator('.slot[data-pile="stock"].suggest-to, .card.suggest').count() >= 1
        box = pg.locator('.slot[data-pile="stock"]').bounding_box()
        pg.mouse.click(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
    pg.wait_for_timeout(400)
    assert 'Moves 1' in status(pg), status(pg)
    assert pg.locator('.card.suggest').count() == 0 and pg.locator('.suggest-to').count() == 0, 'the hint goes once it is taken'
    assert pg.locator('#toast').is_hidden(), 'and so does its message'
    # the H key does the same; the message has a close button; a game with no solver has no Hint
    pg.keyboard.press('h')
    pg.wait_for_selector('.card.suggest, .slot.suggest-to', timeout=20000)
    assert pg.locator('#toast').is_visible()
    pg.click('#toast-close')
    assert pg.locator('#toast').is_hidden(), 'the close button dismisses the message'
    assert pg.locator('.card.suggest, .slot.suggest-to').count() >= 1, 'the lit move stays'
    start(pg, 'yukon')
    pg.click('#options-btn')
    assert pg.locator('#hint-btn').is_hidden(), 'Yukon cannot be searched'
    pg.keyboard.press('Escape')
    # a position the solver cannot win still gets a plausible move, and says so
    start(pg, 'forty')
    pg.keyboard.press('h')
    pg.wait_for_selector('#toast:not([hidden])', timeout=30000)
    text = pg.locator('#toast').inner_text()
    assert 'win is still possible' in text or 'No win found' in text, text
    assert pg.locator('.card.suggest, .slot.suggest-to').count() >= 1


def open_settings(pg):
    pg.click('#options-btn')
    pg.click('#settings-btn')
    assert pg.locator('#settings').is_visible() and not pg.locator('#options').is_visible()


def setting(pg, name, value):
    pg.click(f'#settings button[data-setting="{name}"][data-value="{value}"]')


def root(pg, attribute):
    return pg.evaluate(f"document.documentElement.dataset.{attribute}")


def check_settings(pg):
    start(pg, 'klondike')
    assert (root(pg, 'felt'), root(pg, 'back'), root(pg, 'motion')) == ('green', 'red', 'normal')
    open_settings(pg)
    setting(pg, 'felt', 'blue')
    assert root(pg, 'felt') == 'blue'
    assert pg.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--felt').trim()") == '#2b5a7a'
    assert pg.locator('#settings button[data-setting="felt"][data-value="blue"]').get_attribute('aria-pressed') == 'true'
    assert pg.locator('#settings button[data-setting="felt"][data-value="green"]').get_attribute('aria-pressed') == 'false'
    setting(pg, 'back', 'black')
    assert pg.evaluate("getComputedStyle(document.querySelector('.back-base')).fill") == 'rgb(29, 29, 34)'
    transition = lambda: pg.evaluate("getComputedStyle(document.querySelector('.card.ready')).transitionDuration.split(',')[0]")
    assert transition() == '0.22s'
    setting(pg, 'motion', 'fast')
    assert transition() == '0.11s'
    setting(pg, 'motion', 'off')
    assert transition() == '0s'
    setting(pg, 'motion', 'normal')
    pg.keyboard.press('Escape')
    assert pg.locator('#settings').is_hidden(), 'Escape closes the settings'
    assert pg.evaluate("document.activeElement.id") == 'options-btn'
    pg.reload()
    pg.wait_for_timeout(700)
    assert (root(pg, 'felt'), root(pg, 'back'), root(pg, 'motion')) == ('blue', 'black', 'normal'), 'settings are kept'
    open_settings(pg)
    assert pg.locator('#settings button[data-setting="back"][data-value="black"]').get_attribute('aria-pressed') == 'true'
    assert pg.locator('#settings').is_visible()
    box = pg.locator('#settings').bounding_box()
    table = pg.locator('#table').bounding_box()
    assert box['x'] >= table['x'] and box['x'] + box['width'] <= table['x'] + table['width'] + 1, f'the panel fits the table {box} {table}'
    overflow = pg.evaluate("[...document.querySelectorAll('#settings button')].filter(b => { const p = document.getElementById('settings').getBoundingClientRect(), r = b.getBoundingClientRect(); return r.right > p.right || r.left < p.left; }).length")
    assert overflow == 0, 'no button sticks out of the panel'
    pg.click('#settings-close')
    assert pg.locator('#settings').is_hidden(), 'the close button closes the panel'
    pg.evaluate("localStorage.setItem('baize.settings', JSON.stringify({ felt: 'plaid', back: 'red' }))")
    pg.reload()
    pg.wait_for_timeout(700)
    assert (root(pg, 'felt'), root(pg, 'back')) == ('green', 'red'), 'a value that is not a choice falls back to the default'


def check_animation_setting_overrides_the_device(pg):
    context = pg.context.browser.new_context(viewport={'width': 1000, 'height': 900}, reduced_motion='reduce')
    context.route('**/fonts.googleapis.com/**', lambda route: route.abort())
    page = context.new_page()
    page.goto(URL)
    page.wait_for_timeout(700)
    assert root(page, 'motion') == 'reduced', 'Device follows the system'
    open_settings(page)
    setting(page, 'motion', 'normal')
    assert root(page, 'motion') == 'normal', 'Normal overrides the system'
    page.keyboard.press('Escape')
    check_tap_moves_are_animated(page)
    context.close()


def check_game_menu_gives_up_focus(pg):
    pg.focus('#game')
    pg.select_option('#game', GAMES['golf'])
    pg.wait_for_timeout(900)
    assert pg.evaluate("document.activeElement.id") != 'game', 'rank keys would be typed into the menu'
    pg.keyboard.press('Shift')                       # and the keys reach the game
    pg.keyboard.up('Shift')


def check_win_panel_is_on_top(pg):
    """The plaque that announces a win must not be painted over by cards."""
    for name in ('klondike', 'freecell', 'spider'):
        start(pg, name)
        pg.evaluate("() => { document.getElementById('win').hidden = false; }")
        covered = pg.evaluate("""() => {
            const r = document.querySelector('#win .plaque').getBoundingClientRect();
            const points = [[.1, .1], [.5, .5], [.9, .9], [.1, .9], [.9, .1]];
            return points.filter(([x, y]) => !document.elementFromPoint(r.left + r.width * x, r.top + r.height * y)?.closest('.win')).length;
        }""")
        assert covered == 0, f'{name}: cards paint over the win plaque at {covered} of 5 points'


CHECKS = [check_menu_and_saves, check_shift_highlight, check_rank_keys, check_toggle_persists,
          check_golf_tap_and_undo, check_tap_moves_are_animated, check_animation_survives_a_small_resize, check_diagnostics_panel, check_tap_moves_are_animated_even_with_reduced_motion, check_freecell_drag_and_double_tap, check_rules_card, check_pyramid, check_pyramid_stacking, check_stacking_every_game, check_spider, check_forty_thieves, check_yukon, check_tripeaks, check_redeal_order, check_winnable_deals, check_responsive, check_search_can_be_cancelled, check_page_cannot_zoom, check_statistics, check_settings, check_animation_setting_overrides_the_device, check_hint, check_rules_text_stays_inside_the_frame, check_selected_and_highlighted_combine, check_winnable_preference_is_shared, check_game_menu_gives_up_focus, check_win_panel_is_on_top]

if sys.argv[1:]:                       # run only the checks named on the command line
    CHECKS = [c for c in CHECKS if c.__name__ in sys.argv[1:]]

with sync_playwright() as p:
    browser = p.chromium.launch()
    failures = 0
    for check in CHECKS:
        context = browser.new_context(viewport={'width': 1000, 'height': 900})
        context.route('**/fonts.googleapis.com/**', lambda route: route.abort())
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(URL)
        page.wait_for_timeout(700)
        try:
            check(page)
            assert not errors, errors
            print('ok  ', check.__name__)
        except AssertionError as e:
            failures += 1
            print('FAIL', check.__name__, '-', e)
            traceback.print_exc()
        page.context.close()
    browser.close()
    raise SystemExit(1 if failures else 0)
