"""Browser checks for baize.html (needs Python Playwright with Chromium).

Run from anywhere:  python3 test/ui.test.py
"""
import pathlib
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
        pg.wait_for_timeout(1300)                       # the deal animation staggers by up to 0.7 s
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
        pg.wait_for_timeout(1300)
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


CHECKS = [check_menu_and_saves, check_shift_highlight, check_rank_keys, check_toggle_persists,
          check_golf_tap_and_undo, check_freecell_drag_and_double_tap, check_rules_card, check_pyramid, check_pyramid_stacking, check_stacking_every_game, check_spider, check_forty_thieves]

with sync_playwright() as p:
    browser = p.chromium.launch()
    failures = 0
    for check in CHECKS:
        page = browser.new_context(viewport={'width': 1000, 'height': 900}).new_page()
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
        page.context.close()
    browser.close()
    raise SystemExit(1 if failures else 0)
