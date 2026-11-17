#!/usr/bin/env python3
"""Put 98.css (style.css next to this file, unmodified, MIT: see LICENSE) into baize.html as the Retro style.

98.css styles bare elements (button, select, table, body ...), so the page would change in every style. This turns
each of its selectors into a descendant of html[data-theme="retro"], inlines its fonts and icons as data: URLs, and
writes the result between the 98css markers in baize.html. It leaves out the h1 to h4 rules (the page sets its own
headings). Run it again after changing the 98.css files:  python3 tools/98css/embed.py
"""
import base64, pathlib, re, urllib.parse

HERE = pathlib.Path(__file__).parent
PAGE = HERE.parent.parent / 'baize.html'
SCOPE = 'html[data-theme="retro"]'
LEFT_OUT = {'h1', 'h2', 'h3', 'h4'}                     # the page's own headings stay as they are
START, END = '<!-- 98css:start -->', '<!-- 98css:end -->'


def blocks(css):
    """Split CSS into (prelude, body) pairs at the top level; strings (the svg-load paths) are skipped over."""
    out, i, depth, prelude_from, body_from = [], 0, 0, 0, 0
    prelude = ''
    while i < len(css):
        c = css[i]
        if c in '"\'':
            i = css.index(c, i + 1)
        elif c == '{':
            if depth == 0:
                prelude, body_from = css[prelude_from:i].strip(), i + 1
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                out.append((prelude, css[body_from:i]))
                prelude_from = i + 1
        i += 1
    return out


def scope(selector):
    selector = selector.strip()
    if selector == ':root':
        return SCOPE
    return f'{SCOPE} {selector}'


def rewrite(css, in_media=False):
    out = []
    for prelude, body in blocks(css):
        if prelude.startswith('@font-face'):
            out.append(f'{prelude} {{{body}}}' if not in_media else '')
        elif prelude.startswith('@media'):
            out.append(f'{prelude} {{\n{rewrite(body, True)}}}')
        else:
            selectors = [s.strip() for s in prelude.split(',')]
            kept = [s for s in selectors if s not in LEFT_OUT]
            if kept:
                out.append(f'{",\n".join(scope(s) for s in kept)} {{{body}}}')
    return '\n'.join(part for part in out if part) + '\n'


def inline(css):
    def svg(match):
        data = (HERE / match.group(1)).read_text().strip()
        return f'url("data:image/svg+xml,{urllib.parse.quote(data, safe="/:=, ")}")'
    css = re.sub(r'svg-load\("\./([^"]+)"\)', svg, css)

    def font(match):
        return f'url("data:font/woff2;base64,{base64.b64encode((HERE / 'fonts' / match.group(1)).read_bytes()).decode()}")'
    css = re.sub(r'url\("fonts/converted/([^"]+\.woff2)"\)', font, css)
    css = re.sub(r'\s*src: url\("fonts/[^"]+\.woff"\) format\("woff"\);', '', css)   # woff2 is in every browser the page supports
    return css


def main():
    source = (HERE / 'style.css').read_text()
    source = re.sub(r'/\*.*?\*/', '', source, flags=re.S)
    css = inline(rewrite(source))
    page = PAGE.read_text()
    block = f'{START}\n<style id="retro-98css">\n/* 98.css v0.1.21, Copyright (c) 2020 Jordan Scales, MIT licence: https://github.com/jdan/98.css */\n{css}</style>\n{END}\n'
    if START in page:
        page = re.sub(re.escape(START) + '.*?' + re.escape(END) + '\n', lambda _: block, page, flags=re.S)
    else:
        page = page.replace('<style>\n', block + '<style>\n', 1)
    PAGE.write_text(page)
    print(f'98.css: {len(css):,} bytes written to {PAGE.name}')


if __name__ == '__main__':
    main()
