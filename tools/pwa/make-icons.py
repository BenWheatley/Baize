"""Render icon.svg to the PNG sizes the web app manifest and iOS need.

Run from anywhere:  python3 tools/pwa/make-icons.py
"""
import pathlib
from playwright.sync_api import sync_playwright

here = pathlib.Path(__file__).resolve().parent
svg = (here / 'icon.svg').read_text()
SIZES = {'icon-192.png': 192, 'icon-512.png': 512, 'icon-maskable-512.png': 512, 'apple-touch-icon.png': 180}

with sync_playwright() as p:
    browser = p.chromium.launch()
    for name, size in SIZES.items():
        page = browser.new_page(viewport={'width': size, 'height': size})
        sized = svg.replace('<svg ', f'<svg width="{size}" height="{size}" ', 1)
        page.set_content(f'<body style="margin:0">{sized}</body>')
        page.screenshot(path=str(here.parent.parent / 'icons' / name))
        page.close()
    browser.close()
