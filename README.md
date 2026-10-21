# Baize

A single-page card-table simulator. `baize.html` is the whole app: open it in a browser, or publish it as is. It plays Klondike, FreeCell, Golf, Pyramid, Spider (one, two or four suits; two decks) and Forty Thieves and Yukon (two decks), and the engine is written so that other games (Hanabi, for one) can be added as rulesets.

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

Drives the page in Chromium with Python Playwright: the game menu and saves, highlighting with Shift and rank keys, the Show moves toggle, Golf taps, FreeCell drag and double-tap, Pyramid pairs and kings, Spider and Forty Thieves taps and deals, and the rules card (opening, closing, stacking order). Deals are fixed by seed. One check fails if cards ever get a CSS filter (or a transition on one) again, which is what made highlighting slow. It also checks that a new deal clears the table before dealing, and that winnable deals can be won. It also checks the options menu, the search dialogue and its Cancel, that the page never scrolls or zooms on any screen size, and that a tapped card flies above the others.

## Installing it (PWA)

There is no build step: `baize.html` is already an installable app. Beside it are `manifest.webmanifest`, `sw.js` (a service worker that serves the game from its cache, so it works offline, and refreshes the cache in the background) and `icons/` (drawn for this page, CC0; `tools/pwa/make-icons.py` redraws them from `tools/pwa/icon.svg`). Serve the folder over HTTPS, for example with GitHub Pages, and open `baize.html` (the bare address forwards to it). On an iPad use Safari, then Share and Add to Home Screen; Chrome and Edge offer Install. `python3 test/pwa.test.py` serves the folder locally and checks the manifest, icons, service worker and offline play.

Because the cache is refreshed in the background, an edited page appears the second time the app is opened. The web fonts come from Google Fonts and are cached after the first online visit; without them the page uses system fonts.

## Winnable deals

Klondike, FreeCell, Golf, Pyramid and one-suit Spider offer Deals: Winnable. `solve()` in the engine searches a ruleset's own `moves()` (depth first, or best first where the ruleset gives a `progress()` score); the app runs it on one seed after another, in a worker, until it finds a win, and the stored seed then reproduces that deal. A solution that is found is real, since the tests replay it, but a search that gives up proves nothing: the app stops after 20 seconds and says the deal is random. While it searches, a dialogue with a spinner and a Cancel button covers the table. Yukon, Forty Thieves and two- or four-suit Spider are too hard for this solver, so they do not offer it.

## Card art

The faces are Adrian Kennard's playing cards (<https://www.me.uk/cards/>), dedicated to the public domain under CC0 1.0, taken from `@letele/playing-cards` 0.1.0 (CC0-1.0). The card back is drawn for this page and is also CC0. To regenerate the embedded faces, run `tools/art/build.sh`.

## Working on it

Commit each change on its own, run `npm test` first, and keep diffs small. The history before the first test commit was rebuilt from saved snapshots of each published version, so some early commits bundle several changes.

## Screen behaviour

The page never scrolls or zooms; the cards shrink to fit (down to 22 px wide). Only the rules card scrolls. Browser zoom with Ctrl and +/- is left alone for accessibility.

## Updates

The service worker answers from its cache and checks the server in the background (past the browser's own cache). When baize.html has changed, open pages show "A new version is ready" with a Reload button; the app also checks each time it comes back to the front. An installed iPad app is suspended rather than closed, so without this it would keep the old version indefinitely.
