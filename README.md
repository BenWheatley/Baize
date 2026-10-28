# Baize

A single-page card-table simulator. `baize.html` is the whole app: open it in a browser, or publish it as is. It plays Klondike, FreeCell, Golf, Pyramid, Spider (one, two or four suits; two decks) and Forty Thieves (two decks), Yukon and TriPeaks, and the engine is written so that other games (Hanabi, for one) can be added as rulesets.

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
python3 test/ui.test.py [check_name ...]
```

Drives the page in Chromium with Python Playwright (naming checks on the command line runs only those): the game menu and saves, highlighting with Shift and rank keys, the Show moves toggle, Golf taps, FreeCell drag and double-tap, Pyramid pairs and kings, Spider and Forty Thieves taps and deals, and the rules card (opening, closing, stacking order). Deals are fixed by seed. One check fails if cards ever get a CSS filter (or a transition on one) again, which is what made highlighting slow. It also checks that a new deal clears the table before dealing, and that winnable deals can be won. It also checks the options menu, the search dialogue and its Cancel, that the page never scrolls or zooms on any screen size, and that a tapped card flies above the others.

## Installing it (PWA)

There is no build step: `baize.html` is already an installable app. Beside it are `manifest.webmanifest`, `sw.js` (a service worker that serves the game from its cache, so it works offline, and refreshes the cache in the background) and `icons/` (drawn for this page, CC0; `tools/pwa/make-icons.py` redraws them from `tools/pwa/icon.svg`). Serve the folder over HTTPS, for example with GitHub Pages, and open `baize.html` (the bare address forwards to it). On an iPad use Safari, then Share and Add to Home Screen; Chrome and Edge offer Install. `python3 test/pwa.test.py` serves the folder locally and checks the manifest, icons, service worker and offline play.

Because the cache is refreshed in the background, an edited page appears the second time the app is opened. The web fonts come from Google Fonts and are cached after the first online visit; without them the page uses system fonts.

## Winnable deals

Klondike, FreeCell, Golf, Pyramid, TriPeaks, Yukon, Forty Thieves and one-suit Spider offer Deals: Winnable. `solve()` in the engine searches a ruleset's own `moves()` (depth first, or best first where the ruleset gives a `progress()` score); the app runs it on one seed after another, in a worker, until it finds a win, and the stored seed then reproduces that deal. A solution that is found is real, since the tests replay it, but a search that gives up proves nothing: the app stops after 20 seconds and says the deal is random. While it searches, a dialogue with a spinner and a Cancel button covers the table. Two- and four-suit Spider are too hard for this solver so far. Forty Thieves is only just within reach: its ruleset names positions up to symmetry (`key`: columns and foundations sorted, the two copies of a card alike) and gets a bigger budget (`searchNodes`), and the search then finds a deal in about one seed in eight, so it sometimes uses the whole 20 seconds and gives up, so they do not offer it.

## Card art

The faces are Adrian Kennard's playing cards (<https://www.me.uk/cards/>), dedicated to the public domain under CC0 1.0, taken from `@letele/playing-cards` 0.1.0 (CC0-1.0). The card back is drawn for this page and is also CC0. To regenerate the embedded faces, run `tools/art/build.sh`.

## High-contrast cards

The Card faces setting (in the menu) swaps the standard faces for "jumbo" ones drawn for this page: a white card in a thick black border, the rank and suit as large as the strip of a fanned column allows (26% of a card's height; `FAN_STEP`), once at the top left and once turned round at the bottom right, and the rank again, huge, in the middle; red and black. `tools/jumbo-deck/build.py` draws them (the ranks are paths made from the outlines of DejaVu Sans Condensed Bold, so every device draws the same shapes and no font is loaded; the four suits are drawn in the script) and writes them into `baize.html` between the `contrast-art` markers, about 90 KB. The faces are 5:7 like the table's cards, so nothing is stretched. `useHighContrast` on the deck switches sets and `refreshFaces` redraws the cards on the table. To change the look, edit the constants at the top of the script and run it again.

## Icons

The icons are Google's Material Symbols (outlined, weight 500), licensed under the Apache License 2.0, copied unchanged from `@material-symbols/svg-500` 0.48.1 into an inline SVG sprite near the top of `baize.html`. No font is loaded, so there is nothing to fetch and no fallback glyph. To change the set, edit the list in `tools/icons/embed.mjs`, then run `npm install && node embed.mjs` in `tools/icons`. `NOTICE` and `LICENSE-material-symbols.txt` carry the attribution and the licence text.

## Working on it

Commit each change on its own, run `npm test` first, and keep diffs small. The history before the first test commit was rebuilt from saved snapshots of each published version, so some early commits bundle several changes.

## Screen behaviour

The page never scrolls or zooms; the cards shrink to fit (down to 22 px wide). Only the rules card scrolls. Browser zoom with Ctrl and +/- is left alone for accessibility.

## Updates

The service worker answers from its cache and checks the server in the background (past the browser's own cache). When baize.html has changed, open pages show "A new version is ready" with a Reload button; the app also checks each time it comes back to the front. An installed iPad app is suspended rather than closed, so without this it would keep the old version indefinitely.

## Statistics

The Statistics button (in the menu) shows, for each game, deals played and won, win rate, fewest moves in a win and the winning streak (current and best), kept in the browser's local storage. A deal counts when it is won, or when it is given up (New deal, or a change of options) after at least one move; a restart never counts, and a deal is never counted twice, however often it is undone, redone or reloaded. The bookkeeping is `recordResult` in the engine, tested in Node.

## Hints

Hint (its button in the header, or the H key) searches from the current position on a worker, 12,000 positions at most, with a Cancel button if it takes a while (the dialogue appears after 350 ms and, once up, stays for at least 500 ms, so it never just flashes). The search sees the face-down cards too, so it is not a fair hint, only a useful one. It is best-first, by each ruleset's `progress` score, and has two possible results (`hintLine` in the engine):

- a line that wins: its first move is lit (a ring on the cards to move, dashes where they go) and the message says a win is still possible;
- otherwise the line to the best position it reached, one that scores higher than the player's: its first move is lit, and the message says no win was found and the move heads for the best position.

If neither exists, the hint turns the stock where there is one, or says there is nothing to gain. The first move of the ruleset's own move list is never offered as a plain "plausible move": that is what once made hints shuffle runs between equal columns without end.

Hints do not change their minds. `HintBook` remembers every line found, for the position it came from and for each position along it, so following the hints follows one plan and needs no further search; asking twice at the same position, or asking at the first move of a deal chosen by the winnable search (which already found a line), searches nothing. A line that only gains ground is used only if its first move reaches a position not yet seen in this deal. To keep lines short, the search remembers every move it tried and takes the shortest route through them; because a position key may treat positions as equal that are not identical (FreeCell's cells), that route is replayed and the search's own route is used if it fails. Tested in Node: hints followed for 50 moves in Klondike never send a card straight back, and every line found in every game plays out on the real position.

The message stays until the player moves, undoes, deals or presses its × button. The lit cards keep their place in the stack: a hint does not lift them above their neighbours. Games whose ruleset has no `moves()` have no Hint (every game has one now).

## Controls

Nothing is nested: the menu button (the hamburger) opens one flat panel, and no button in it opens another menu inside it. The header is one row: the title plate (Baize, with the current game as a small subtitle inside it) at the left, then Show moves (a toggle, the touch screen's answer to holding Shift), Hint, Undo, Auto-finish (always there, faded when there is nothing to finish), New deal (red, like every destructive action) and the menu button at the far right. Below 780 px wide the buttons keep only their icons; below 560 px the title plate takes a row of its own, spanning the width with the game name at its right; below 380 px New deal is an icon too. The menu holds everything else: Rules and Statistics (these open their own panel in place of the menu), the game picker, the game's own options (changing one deals again), Restart this deal (red; it discards progress, so it is out of reach of a stray tap), and the appearance choices.

**Sending cards home.** A double tap sends a card home (`onActivate`). A card dragged and let go within one and a half card widths of its foundation also goes home if nothing nearer took it (`homeAction` in a ruleset, `NEAR_HOME` in the script; Klondike, FreeCell, Yukon and Forty Thieves). The *Safe cards* setting (menu, Preferences; shown only for games whose ruleset has `safeAction`: Klondike and FreeCell) plays by itself, after each move, every card that can never be needed on the tableau: aces and twos, and any other card once both cards of the opposite colour one rank lower are home (`isSafeHome`). It is off by default. The cards it plays are recorded with `auto: true`, so Undo takes the whole run back together with the move that began it.

## Panels

Statistics, Settings and the Rules card are managed together (`PANELS`, `showPanel`, `closePanel` and `togglePanel` in the page script), so at most one is open: opening one closes another, and pressing a button whose panel is open closes it. The modal ones (Statistics, Cleared, the search dialogue) are fixed to the window, not placed inside the table, so a small screen does not squeeze them. Every panel has the same × button (`.icon-close`), the same title size and the same button padding (`--btn-pad`). The win screen ("Cleared") is the Statistics panel opened in its won mode, with the results of the deal just played; it has no copy of its own. While it is open the other panels' buttons are disabled, and it closes with ×, Escape or any move that undoes the win. Below 560 px wide the header buttons show only their icons (the words stay as accessible names).

## Styles

The Style setting offers Steampunk (the walnut-and-brass original and the base of all the CSS), Cyberpunk (black glass with neon edges, monospaced capitals), Sci-fi (flat rounded console panels in an LCARS-like palette, black ground) and Retro (a 1990s desktop: teal ground, grey bevelled windows, navy title bars, Tahoma). The script writes the choice to `data-theme` on the page, and each non-default style is one block at the end of the stylesheet that replaces the colour and font tokens and the few rules that carry the look: the desk (`--desk`), the title plate, buttons, segmented choices, rail, table, slots and panels. Table colour and card back are independent of the style. Scrollbars follow the style through `--scroll-thumb` and `--scroll-track` (`scrollbar-color`); Retro draws a chequered trough and bevelled thumb where the browser allows. A panel's side padding belongs to its title and its `.plaque-body`, not to the plaque, so a scrollbar sits at the panel's edge; `check_scrollbars_sit_at_the_panel_edge` measures this (with classic scrollbars) at three widths in every style. To add a style, add its value to `SETTINGS` in the engine, a colour for it in `THEME_COLOURS` (the browser's bar), and a block in the stylesheet; `check_styles` covers every choice.

## Menu

The hamburger button in the header opens one panel: Rules and Statistics, the game picker, the current game's own options (Draw, Deals, ...), Restart this deal, and the appearance choices: style, table colour, card back colour and animation. Animation is Device (follow the system's Reduce Motion), Normal, Fast (half the time) or Off; the script writes the result to `data-motion` on the page, which the CSS keys on, so choosing Normal also overrides a system that reports Reduce Motion wrongly (as an installed iPad app can). The choices are kept in local storage under `baize.settings`. `SETTINGS` and `readSettings` in the engine define them and drop any stored value that is not one of the choices; the colours themselves are `html[data-felt=...]` and `html[data-back=...]` rules in the CSS. The panel is a popover (the HTML `popover` attribute, in the browser's top layer so nothing clips it) hung from the menu button and placed by `placeMenu` in the script, rather than a dialogue, so the new colours can be seen behind it; it closes with its × button or Escape. Changing a game option, or the game, leaves the panel open, so another can be tried.
