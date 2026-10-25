"""Prepares the card faces of the high-contrast deck from a checkout of https://github.com/saulspatz/SVGCards
(public domain), folder Decks/Accessible/Horizontal/svgs.

Numbers and aces are used as drawn. The court cards' portraits are traced artwork of 100-400 KB each, and
they are also the hardest part of a card to read, so each portrait is replaced by one large letter in the
suit's colour above a small suit mark.

usage: python3 prepare.py SVGCARDS_CHECKOUT OUT_DIR      then: node build.mjs OUT_DIR
"""
import os, shutil, sys
import xml.etree.ElementTree as ET

SRC = os.path.join(sys.argv[1], 'Decks/Accessible/Horizontal/svgs/')
OUT = sys.argv[2]
NS = 'http://www.w3.org/2000/svg'
ET.register_namespace('', NS)
for prefix, uri in [('xlink', 'http://www.w3.org/1999/xlink'), ('rdf', 'http://www.w3.org/1999/02/22-rdf-syntax-ns#'),
                    ('cc', 'http://creativecommons.org/ns#'), ('dc', 'http://purl.org/dc/elements/1.1/')]:
    ET.register_namespace(prefix, uri)
COLOUR = {'spade': '#000', 'heart': '#ff0052', 'diamond': '#00f', 'club': '#228b22'}
LETTER = {'Jack': 'J', 'Queen': 'Q', 'King': 'K'}
tag = lambda name: '{%s}%s' % (NS, name)

os.makedirs(OUT, exist_ok=True)
for suit, colour in COLOUR.items():
    for name in ['Ace', *range(2, 11)]:
        shutil.copy(f'{SRC}{suit}{name}.svg', OUT)
    ace = ET.parse(f'{SRC}{suit}Ace.svg').getroot()
    ace_shift = [g for g in ace if g.tag == tag('g')][0].attrib.get('transform', '')
    pip = [e for e in ace.iter() if (e.attrib.get('id') or '').endswith('Pip')][0]
    for name, letter in LETTER.items():
        tree = ET.parse(f'{SRC}{suit}{name}.svg')
        root = tree.getroot()
        card = [g for g in [g for g in root if g.tag == tag('g')][0] if g.tag == tag('g')][0]
        for child in list(card):
            if child.tag == tag('g') and len(ET.tostring(child)) > 20000:
                card.remove(child)                                   # the portrait
        for meta in [e for e in root if e.tag == tag('metadata')]:
            root.remove(meta)
        mark = ET.SubElement(root, tag('g'))
        mark.set('transform', f'translate(105 216) scale(.5) translate(-105 -155) {ace_shift}')
        mark.append(pip)
        text = ET.SubElement(root, tag('text'))
        text.attrib.update({'x': '105', 'y': '176', 'text-anchor': 'middle', 'font-family': 'Arial, Helvetica, sans-serif',
                            'font-weight': '700', 'font-size': '118', 'fill': colour})
        text.text = letter
        tree.write(f'{OUT}/{suit}{name}.svg')
