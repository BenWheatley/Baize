# Baize

A single-page card-table simulator. `baize.html` is the whole app: open it in a browser, or publish it as is. It plays Klondike, FreeCell, Golf, Pyramid, Spider (one, two or four suits; two decks) and Forty Thieves (two decks), and the engine is written so that other games (Hanabi, for one) can be added as rulesets.

'Baize' is the green woollen cloth that covers a card table.

## Layout of `baize.html`

| Script id | Contents |
| --- | --- |
| `engine` | Piles, actions, `Session` (replayable, with undo), `movableCards`, and the rulesets. No DOM access. |
| `deck-art` | The 52 card faces as SVG strings (generated, about 440 kB). |
| `deck` | A deck: `face(card)`, `back()`, `label(card)`. |
| `app` | Table drawing, pointer and keyboard input, saves, page controls. |

A ruleset's contract is described in the comment above the `engine` script.

A game is stored as (ruleset, options, seed, actions) and the position is replayed from that, so a saved game cannot hold an illegal position.

## Tests

```sh
npm test
```

Runs the engine, rulesets and deck art in Node (about 30 seconds, mostly random playouts and solver runs). There are no dependencies to install.

```sh
python3 test/ui.test.py
```

Drives the page in Chromium with Python Playwright: the game menu and saves, highlighting with Shift and rank keys, the Show moves toggle, Golf taps, FreeCell drag and double-tap, Pyramid pairs and kings, Spider and Forty Thieves taps and deals, and the rules card (opening, closing, stacking order). Deals are fixed by seed. One check fails if cards ever get a CSS filter (or a transition on one) again, which is what made highlighting slow. It also checks that a new deal clears the table before dealing, and that winnable deals can be won.

## Installing it (PWA)

`npm run build:pwa` writes `dist/`: a complete page around `baize.html`, a web app manifest, a service worker that makes the game work offline, and the icons (`tools/pwa/icons`, drawn for this page and CC0; `tools/pwa/make-icons.py` redraws them from `icon.svg`). Put `dist/` on any HTTPS static host, for example GitHub Pages. On an iPad open the address in Safari, then Share and Add to Home Screen; Chrome and Edge offer Install. `python3 test/pwa.test.py` serves `dist/` locally and checks the manifest, icons, service worker and offline play.

The service worker caches the page by content hash, so a rebuilt page replaces the old one the next time the app is opened online. The web fonts come from Google Fonts and are cached only after the first online visit; without them the page uses system fonts.

## Winnable deals

Klondike, FreeCell, Golf, Pyramid and one-suit Spider offer Deals: Winnable. `solve()` in the engine searches a ruleset's own `moves()` (depth first, or best first where the ruleset gives a `progress()` score); the app runs it on one seed after another, in a worker, until it finds a win, and the stored seed then reproduces that deal. A solution that is found is real, since the tests replay it, but a search that gives up proves nothing: the app stops after 20 seconds and says the deal is random. Forty Thieves and two- or four-suit Spider are too hard for this solver, so they do not offer it.

## Card art

The faces are Adrian Kennard's playing cards (<https://www.me.uk/cards/>), dedicated to the public domain under CC0 1.0, taken from `@letele/playing-cards` 0.1.0 (CC0-1.0). The card back is drawn for this page and is also CC0. To regenerate the embedded faces, run `tools/art/build.sh`.

## Working on it

Commit each change on its own, run `npm test` first, and keep diffs small. The history before the first test commit was rebuilt from saved snapshots of each published version, so some early commits bundle several changes.
