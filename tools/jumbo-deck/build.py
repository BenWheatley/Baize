"""Draws the high-contrast "jumbo" card faces and writes them into baize.html between the contrast-art markers.

Every face is the same plain design: a white card in a thick black border, the rank and suit as big as the strip of a
fanned card allows (the table shows 26% of a card's height of every face-up card in a column), once at the top left and
once turned round at the bottom right, and nothing else. The ranks are the outlines of DejaVu Sans Condensed Bold
(free licence, see NOTICE), made into paths so every device draws the same shapes and no font has to be loaded; the
suits are drawn here.

usage: python3 build.py            (needs fontTools and the DejaVu font; the file is changed in place)
"""
import json, re, sys
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf'
BLACK, RED = '#000', '#e0200b'
W, H = 240, 336                        # the table's cards are 5:7
DIGIT = 76                             # height of the rank
TOP = 11                               # distance from the top of the card to the top of the index
GAP = 8                                # between rank and suit
LEFT = 17
SQUEEZE = 0.88                         # narrower than the font's own condensed shapes

font = TTFont(FONT)
cmap = font.getBestCmap()
glyphs = font.getGlyphSet()
metrics = font['hmtx']
from fontTools.pens.boundsPen import BoundsPen
bounds = BoundsPen(glyphs)
glyphs[cmap[ord('H')]].draw(bounds)
cap = bounds.bounds[3]                 # height of a capital, which the digits match
scale = DIGIT / cap

def rank_path(label):
    """The outlines of the characters of a rank, as one path, with its top-left at (LEFT, TOP); and its width."""
    pen = SVGPathPen(glyphs, ntos=lambda v: f'{v:.1f}'.rstrip('0').rstrip('.'))
    box = BoundsPen(glyphs)
    for ch in label:
        glyphs[cmap[ord(ch)]].draw(box)
    k = min(scale, DIGIT / (box.bounds[3] - box.bounds[1]))   # J and Q hang below the line: shrink them to stay inside the strip
    x = LEFT
    for ch in label:
        name = cmap[ord(ch)]
        tpen = TransformPen(pen, (k * SQUEEZE, 0, 0, -k, x, TOP + box.bounds[3] * k))
        glyphs[name].draw(tpen)
        x += metrics[name][0] * k * SQUEEZE
    return pen.getCommands(), x - LEFT

def big_rank(label):
    """The rank again, as large as BIG_W x BIG_H allows, centred on the card (a path in card coordinates)."""
    def draw(pen, k, x0, y0):
        x = x0
        for ch in label:
            name = cmap[ord(ch)]
            glyphs[name].draw(TransformPen(pen, (k, 0, 0, -k, x, y0)))
            x += metrics[name][0] * k
    box = BoundsPen(glyphs)
    draw(box, 1, 0, 0)
    x0, y0, x1, y1 = box.bounds
    k = min(BIG_W / (x1 - x0), BIG_H / (y1 - y0))
    pen = SVGPathPen(glyphs, ntos=lambda v: f'{v:.1f}'.rstrip('0').rstrip('.'))
    draw(pen, k, W / 2 - (x0 + x1) / 2 * k, H / 2 - (y0 + y1) / 2 * k)
    return pen.getCommands()

SUITS = {   # each in a 100 x 100 box
    'heart': '<path d="M50 96C10 64 2 44 2 28 2 12 15 3 29 3c9 0 17 5 21 14 4-9 12-14 21-14 14 0 27 9 27 25 0 16-8 36-48 68z"/>',
    'diamond': '<path d="M50 0 92 50 50 100 8 50z"/>',
    'spade': '<path d="M50 2C86 32 98 50 98 66c0 14-11 24-25 24-9 0-17-5-21-13 1 10 5 18 12 23H36c7-5 11-13 12-23-4 8-12 13-21 13C13 90 2 80 2 66 2 50 14 32 50 2z"/>',
    'club': '<circle cx="50" cy="26" r="24"/><circle cx="24" cy="62" r="24"/><circle cx="76" cy="62" r="24"/><path d="M50 40 36 100h28z"/><circle cx="50" cy="56" r="13"/>',
}
BIG_W, BIG_H = 190, 142                # the box in the middle that the huge rank fills: between the two indices, inside the border
SUIT_SIZE = 78                         # at most; the suit shrinks beside a two-digit rank so it stays on the card
LABEL = {1: 'A', 11: 'J', 12: 'Q', 13: 'K'}

def face(suit, rank):
    colour = RED if suit in ('heart', 'diamond') else BLACK
    label = LABEL.get(rank, str(rank))
    path, width = rank_path(label)
    size = min(SUIT_SIZE, W - 22 - (LEFT + width + GAP))
    k = size / 100
    index = (f'<path d="{path}" stroke-width="3" stroke-linejoin="round"/>'
             f'<g transform="translate({LEFT + width + GAP:.1f} {TOP - (size - DIGIT) / 2:.1f}) scale({k:.3f})">{SUITS[suit]}</g>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="none" viewBox="0 0 {W} {H}">'
            f'<rect x="5" y="5" width="{W - 10}" height="{H - 10}" rx="24" fill="#fff" stroke="#000" stroke-width="10"/>'
            f'<g fill="{colour}" stroke="{colour}">{index}<g transform="rotate(180 {W / 2} {H / 2})">{index}</g>'
            f'<path d="{big_rank(label)}" stroke-width="3" stroke-linejoin="round"/></g></svg>')

art = {f'{suit[0]}{rank}': face(suit, rank) for suit in SUITS for rank in range(1, 14)}
block = ('<!-- contrast-art:start -->\n<script id="deck-art-contrast">\nconst CONTRAST_ART = '
         + json.dumps(art, separators=(',', ':')) + ';\n</script>\n<!-- contrast-art:end -->')
if len(sys.argv) > 1 and sys.argv[1] == '--json':
    json.dump(art, open(sys.argv[2], 'w'))
    sys.exit()
path = __file__.rsplit('/', 2)[0] + '/../baize.html'
html = open(path, encoding='utf8').read()
new, n = re.subn(r'<!-- contrast-art:start -->.*<!-- contrast-art:end -->', lambda m: block, html, flags=re.S)
assert n == 1, 'contrast-art markers not found'
open(path, 'w', encoding='utf8').write(new)
print('bytes', len(block))
