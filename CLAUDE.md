# Baize

Single-file card-game simulator (`baize.html`), published as an artifact and as an installable PWA. See `README.md`.

## When finishing a task
- Tick it off in `TODO.md` (move it to Done), and add any follow-ups it revealed.
- Update `README.md` for anything a player or a maintainer would need to know.
- Commit each change separately and keep diffs small; run `npm test`, and `python3 test/ui.test.py` and `python3 test/pwa.test.py` for anything touching the page.
- Deliver as `git format-patch --binary` files; republish the artifact.
- Refactors must leave `test/golden.json` unchanged. Regenerate it (`node test/golden.test.js --update`) only for a deliberate rule change.
