"""Checks that baize.html, served as it is, is installable and works offline.

Run from anywhere:  python3 test/pwa.test.py
"""
import functools
import http.server
import json
import pathlib
import threading
from playwright.sync_api import sync_playwright

DIST = pathlib.Path(__file__).resolve().parent.parent

class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


handler = functools.partial(Quiet, directory=str(DIST))
server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
base = f'http://127.0.0.1:{server.server_port}/baize.html'
root = f'http://127.0.0.1:{server.server_port}/'

with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context(viewport={'width': 1000, 'height': 900})
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(base)
    page.wait_for_function('navigator.serviceWorker.controller || navigator.serviceWorker.ready.then(() => true)')
    page.evaluate('navigator.serviceWorker.ready')
    page.reload()                                   # now controlled by the worker
    page.wait_for_timeout(500)
    assert page.evaluate('Boolean(navigator.serviceWorker.controller)'), 'the service worker controls the page'

    manifest = page.evaluate("fetch(document.querySelector('link[rel=manifest]').href).then(r => r.json())")
    assert page.evaluate('document.compatMode') == 'CSS1Compat', 'the page is not in quirks mode'
    assert manifest['start_url'] == 'baize.html'
    assert manifest['display'] == 'standalone' and manifest['name'] == 'Baize', manifest
    sizes = {icon['sizes'] for icon in manifest['icons']}
    assert {'192x192', '512x512'} <= sizes, sizes
    assert any(icon['purpose'] == 'maskable' for icon in manifest['icons'])
    for icon in manifest['icons']:
        assert page.evaluate(f"fetch('{icon['src']}').then(r => r.ok)"), icon['src']
    page.goto(root)                                  # the bare address forwards to the game
    page.wait_for_url('**/baize.html')
    page.goto(base)
    assert page.evaluate("fetch(document.querySelector('link[rel=apple-touch-icon]').href).then(r => r.ok)")
    assert page.evaluate("document.querySelector('meta[name=apple-mobile-web-app-capable]').content") == 'yes'

    # Offline: the whole app still opens and plays.
    context.set_offline(True)
    page.goto(base)
    page.wait_for_timeout(800)
    assert page.locator('.card').count() > 0, 'the table is dealt while offline'
    page.click('#new')
    page.wait_for_function("!document.getElementById('board').dataset.dealing", timeout=10000)
    assert page.locator('.card').count() > 0
    assert not errors, errors
    browser.close()
server.shutdown()
print('ok   baize.html installs and runs offline')
