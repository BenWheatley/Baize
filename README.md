# Baize

A single-page card-table simulator. `baize.html` is the whole app: open it in a browser, or publish it as is. It plays Klondike, FreeCell and Golf, and the engine is written so that other games (Hanabi, for one) can be added as rulesets.

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

Runs the engine, rulesets and deck art in Node (about 45 seconds, mostly random playouts). There are no dependencies to install.

## Card art

The faces are Adrian Kennard's playing cards (<https://www.me.uk/cards/>), dedicated to the public domain under CC0 1.0, taken from `@letele/playing-cards` 0.1.0 (CC0-1.0). The card back is drawn for this page and is also CC0. To regenerate the embedded faces, run `tools/art/build.sh`.

## Working on it

Commit each change on its own, run `npm test` first, and keep diffs small. The history before the first test commit was rebuilt from saved snapshots of each published version, so some early commits bundle several changes.
