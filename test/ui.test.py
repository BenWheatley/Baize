"""Browser checks for baize.html (needs Python Playwright with Chromium).

Run from anywhere:  python3 test/ui.test.py
"""
import pathlib
from playwright.sync_api import sync_playwright

URL = (pathlib.Path(__file__).resolve().parent.parent / 'baize.html').as_uri()
GAMES = {'klondike': '0', 'freecell': '1', 'golf': '2'}
FACE_DOWN = 'Face-down card'

# Deals are fixed so that the checks do not depend on luck. Seed 1 of FreeCell has three
# movable aces; seed 14 of Golf has two playable column cards.
SEEDS = {'klondike': 7, 'freecell': 1, 'golf': 14}


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
    assert names == ['Klondike', 'FreeCell', 'Golf'], names
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


CHECKS = [check_menu_and_saves, check_shift_highlight, check_rank_keys, check_toggle_persists,
          check_golf_tap_and_undo, check_freecell_drag_and_double_tap]

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
