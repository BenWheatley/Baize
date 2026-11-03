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
- 12. Solvers for every game that can have one: Forty Thieves, Yukon, and Spider with one, two and four suits (`docs/spider-four-suits.md`); Klondike, FreeCell, Golf, Pyramid and TriPeaks already had them

## Open
- 13. WebAssembly: Forty Thieves and Spider searches are in `tools/wasm` (one core, a rules file per game) and embedded in `baize.html` (one file, as decided); hints from any position use them. Next: the same for more games where the JavaScript search is slow (Klondike, FreeCell) if their Winnable or hint success needs it; dominance rules and a learned score for Spider (see the open questions of the write-up)
- 8. More games: Canfield, Beleaguered Castle, Baker's Dozen, Scorpion, Accordion (not Clock: it has no decisions); Hanabi (multiplayer, hidden information) much later

## Follow-ups
- Safe cards for Yukon too (the rule is the same); a drop near a foundation for Golf-style games does not apply
- Accessibility: a card-size setting (the page does not allow pinch zoom); a screen-reader pass with real VoiceOver/NVDA; a keyboard shortcut for the menu

## Conventions for new games
- Where a game can be solved, offer a hint (`moves`) and the shared `WINNABLE_OPTION`, and say in the TODO if a solver is not worth building; it defaults to Winnable (`default: 1`), as every game's does.

## Resolved
- iPad bottom band: fixed by the black status bar style.
