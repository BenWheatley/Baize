#!/usr/bin/env python3
"""Put forty.wasm into baize.html, as base64 between the wasm markers of the solver-wasm script. Run build.sh first."""
import base64, pathlib, re

here = pathlib.Path(__file__).resolve().parent
page = here.parent.parent / 'baize.html'
data = base64.b64encode((here / 'forty.wasm').read_bytes()).decode()
html = page.read_text(encoding='utf8')
new, n = re.subn(r"(/\* wasm:start \*/ )'[^']*'( /\* wasm:end \*/)", lambda m: f"{m.group(1)}'{data}'{m.group(2)}", html)
assert n == 1, 'wasm markers not found'
page.write_text(new, encoding='utf8')
print('bytes', len(data))
