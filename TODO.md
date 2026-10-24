# To do

Kept in the repository so the list survives between sessions. Numbers follow the original list of ideas.

## Done
- 1. Statistics and win tracking
- 2. Hints (solver-backed)
- 7. Settings panel: table colour, card back colour, animation (device, normal, fast, off)
- 9. Panels: one open at a time, shared × / title / padding, Cleared screen is the Statistics panel
- 10. One flat menu (hamburger) holding the game picker, Rules, Statistics, options, Restart and appearance
- 5. Cleanup: shared engine helpers and `defineRules` (backed by `test/golden.test.js`), unused CSS removed, one tap helper in the browser tests; the card art has nothing unused

## Open
- 3. Drag and tap polish: auto-move to a foundation when a card is dropped near one; an "auto-play safe cards home" option for Klondike and FreeCell
- 4. Daily deal: a seeded deal of the day, the same for everyone, with its own win record
- 6. Accessibility: keyboard play (arrow keys and Enter), screen-reader announcements for moves, a high-contrast card option
- 8. More games: Canfield, Beleaguered Castle, Baker's Dozen, Scorpion, Clock, Accordion; Hanabi (multiplayer, hidden information) much later

## Conventions for new games
- Where a game can be solved, offer the shared `WINNABLE_OPTION`; it defaults to Winnable (`default: 1`), as every game's does.

## Resolved
- iPad bottom band: fixed by the black status bar style.
