"""Browser checks for baize.html (needs Python Playwright with Chromium).

Run from anywhere:  python3 test/ui.test.py
"""
import pathlib
import traceback
from playwright.sync_api import sync_playwright

URL = (pathlib.Path(__file__).resolve().parent.parent / 'baize.html').as_uri()
GAMES = {'klondike': '0', 'freecell': '1', 'golf': '2', 'pyramid': '3', 'spider': '4', 'forty': '5'}
FACE_DOWN = 'Face-down card'

# Deals are fixed so that the checks do not depend on luck. Seed 1 of FreeCell has three
# movable aces; seed 14 of Golf has two playable column cards; seed 2 of Pyramid has exactly one
# pair (queen and ace of spades) and one king (hearts) in the free bottom row; seed 30 of Spider
# (one suit) has exactly one tap-move: the six of spades onto the seven; seed 8 of Forty Thieves
# has exactly one, the two of hearts onto the three, and no ace showing.
SEEDS = {'klondike': 7, 'freecell': 1, 'golf': 14, 'pyramid': 2, 'spider': 30, 'forty': 8}


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


def wait_for_deal(pg):
    """Wait until a redeal (cards gathered, then dealt out) has finished."""
    pg.wait_for_timeout(100)
    pg.wait_for_function("!document.getElementById('board').dataset.dealing", timeout=10000)
    pg.wait_for_timeout(300)


def check_menu_and_saves(pg):
    names = pg.eval_on_selector_all('#game option', 'o => o.map(x => x.textContent)')
    assert names == ['Klondike', 'FreeCell', 'Golf', 'Pyramid', 'Spider', 'Forty Thieves'], names
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
    moving = [s for s in track if (s['x'], s['y']) != (track[0]['x'], track[0]['y']) and (s['x'], s['y']) != (track[-1]['x'], track[-1]['y'])]
    assert len(moving) >= 3, f'the card should be seen part-way along its path: {len(moving)} samples'
    assert all(s['z'] >= 60000 for s in moving), 'it flies above the other cards'
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
    assert pg.locator('.slot').count() == 2, 'only the stock and waste have outlines'
    shift(pg, True)
    assert lit(pg) == sorted([FACE_DOWN, 'Ace of spades', 'King of hearts', 'Queen of spades']), lit(pg)
    shift(pg, False)

    def tap(label):
        b = pg.locator(f'.card[aria-label="{label}"]').bounding_box()
        pg.mouse.click(b['x'] + b['width'] / 2, b['y'] + b['height'] / 2)
        pg.wait_for_timeout(250)

    tap('Queen of spades')
    assert pg.locator('.card.selected').count() == 1, 'the first card of a pair is selected'
    tap('Ace of spades')
    assert 'Left 26 / 28' in status(pg) and 'Moves 1' in status(pg), status(pg)
    assert pg.locator('.card[aria-label="Ace of spades"]').count() == 0, 'removed cards leave the table'
    tap('King of hearts')
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
    tap(bottom[0])
    tap(bottom[1])
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

    def tap(card_id):
        b = pg.locator(f'.card[data-id="{card_id}"]').bounding_box()
        pg.mouse.click(b['x'] + b['width'] / 2, b['y'] + b['height'] * 0.2)
        pg.wait_for_timeout(300)

    tap('s6.2')
    assert pg.locator('.card.selected').count() == 1, 'the first tap selects'
    tap('s7.2')
    assert 'Moves 1' in status(pg), status(pg)
    pg.click('#undo')
    pg.wait_for_timeout(300)
    box = pg.locator('.slot[data-pile="stock"]').bounding_box()
    pg.mouse.click(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
    pg.wait_for_timeout(500)
    assert 'Deals left 4' in status(pg) and 'Moves 1' in status(pg), status(pg)
    problems = pg.evaluate(STACKING_PROBLEMS)
    assert not problems, problems[:3]


def check_forty_thieves(pg):
    start(pg, 'forty')
    assert 'Home 0 / 104' in status(pg) and 'Stock 64' in status(pg), status(pg)
    assert pg.locator('.card').count() == 104

    def tap(card_id):
        b = pg.locator(f'.card[data-id="{card_id}"]').bounding_box()
        pg.mouse.click(b['x'] + b['width'] / 2, b['y'] + b['height'] * 0.2)
        pg.wait_for_timeout(300)

    tap('h2.1')
    tap('h3.1')
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
    assert pg.evaluate("getComputedStyle(document.getElementById('rules')).overflowY") == 'auto'
    assert pg.evaluate("getComputedStyle(document.getElementById('rules')).touchAction") == 'pan-y'
    assert pg.evaluate("getComputedStyle(document.body).touchAction") == 'none'
    # Ctrl and the wheel, and a double-click, are not allowed to zoom
    prevented = pg.evaluate("""() => [new WheelEvent('wheel', { ctrlKey: true, cancelable: true, bubbles: true }),
        new Event('gesturestart', { cancelable: true, bubbles: true })].map(e => { document.body.dispatchEvent(e); return e.defaultPrevented; })""")
    assert prevented == [True, True], prevented


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
          check_golf_tap_and_undo, check_tap_moves_are_animated, check_freecell_drag_and_double_tap, check_rules_card, check_pyramid, check_pyramid_stacking, check_stacking_every_game, check_spider, check_forty_thieves, check_redeal_order, check_winnable_deals, check_responsive, check_search_can_be_cancelled, check_page_cannot_zoom, check_game_menu_gives_up_focus, check_win_panel_is_on_top]

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
