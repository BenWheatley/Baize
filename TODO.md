# To do

Kept in the repository so the list survives between sessions. Numbers follow the original list of ideas.

## Done
- 1. Statistics and win tracking
- 2. Hints (solver-backed)
- 7. Settings panel: table colour, card back colour, animation (device, normal, fast, off)
- 9. Panels: one open at a time, shared × / title / padding, Cleared screen is the Statistics panel
- 10. One flat menu (hamburger) holding the game picker, Rules, Statistics, options, Restart and appearance
- 11. Styles: Steampunk, Cyberpunk, Sci-fi, Retro (the Style setting)
- 6. Accessibility: keyboard play, screen-reader labels and announcements, inert modals, high-contrast faces (our own jumbo deck), prefers-contrast
- 3. Drag and tap polish: a card let go near its foundation goes home; the Safe cards setting plays safe cards home for Klondike and FreeCell
- 5. Cleanup: shared engine helpers and `defineRules` (backed by `test/golden.test.js`), unused CSS removed, one tap helper in the browser tests; the card art has nothing unused

## Open
- 4. Daily deal: a seeded deal of the day, the same for everyone, with its own win record
- 12. Solvers for the games that lack one (each gets `moves`, `key`, `progress` and `canSolve`, `WINNABLE_OPTION` where it can find deals, and a golden/engine test):
  - Done: Forty Thieves (symmetric position key, 6000 nodes per seed; about one seed in eight solved, so the 20 s search still fails now and then: a pool of seeds found offline would remove that, and would suit Spider too)
  - Spider with two and four suits: hints work, winnable is offered for one suit only; needs a better heuristic (runs in suit, empty columns, hidden cards) and a measured success rate
  - Done: Yukon (about 60% of seeds solved within 3000 nodes). Klondike, FreeCell, Golf, Pyramid and TriPeaks already offered both
- 13. WebAssembly: the Forty Thieves search is in `tools/wasm` and embedded in `baize.html` (one file, as decided). Next: the same for two- and four-suit Spider (it needs a better score first), and hints from any position (the C search takes only a fresh deal)
- 8. More games: Canfield, Beleaguered Castle, Baker's Dozen, Scorpion, Clock, Accordion; Hanabi (multiplayer, hidden information) much later

## Follow-ups
- Safe cards for Yukon too (the rule is the same); a drop near a foundation for Golf-style games does not apply
- Accessibility: a card-size setting (the page does not allow pinch zoom); a screen-reader pass with real VoiceOver/NVDA; a keyboard shortcut for the menu

## Conventions for new games
- Where a game can be solved (or has no decisions, like Clock), offer a hint (`moves`) and the shared `WINNABLE_OPTION`, and say in the TODO if a solver is not worth building; it defaults to Winnable (`default: 1`), as every game's does.

## Resolved
- iPad bottom band: fixed by the black status bar style.
