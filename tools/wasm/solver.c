/* The C solvers of baize.html, as one WebAssembly module: core.h is the search, forty.h and spider.h are the rules.
   The caller writes a position to `image`, calls solve(game, nodes), and reads `path` (see core.h). */

#include "core.h"
#include "forty.h"
#include "spider.h"

enum { FORTY = 0, SPIDER = 1 };

static const Rules *rules_of(int game) { return game == SPIDER ? &spider_rules : &forty_rules; }

int image_address(void) { return (int)(long)image; }
int path_address(void) { return (int)(long)path; }
int expansions_done(void) { return expansions; }
int nodes_made(void) { return node_count; }
int gaps_address(void) { return (int)(long)&spider_gaps; }
int tuning_address(void) { return (int)(long)tuning; }

/* The search with the game's own knobs, or with whatever is in `tuning` (for experiments and tests). */
int solve(int game, int budget) {
  const Rules *r = rules_of(game);
  for (int i = 0; i < 32; i++) tuning[i] = r->defaults[i];
  return search(r, budget);
}
int solve_tuned(int game, int budget) { return search(rules_of(game), budget); }

/* ---- for the tests: any position in, and what this program makes of it out (test/engine.test.js compares it
   with the JavaScript rules) ---- */

static u8 loaded[MAX_STATE];

void load_position(int game) {
  for (int i = 0; i < 32; i++) tuning[i] = rules_of(game)->defaults[i];       /* the score reads its weights from there */
  rules_of(game)->load(image, loaded);
}

/* The moves of the loaded position, as kind, move and extra bytes in `path`; how many. */
int position_moves(int game) {
  Move list[MAX_MOVES];
  int count = rules_of(game)->moves(loaded, list);
  for (int i = 0; i < count; i++) { path[3 * i] = list[i].kind; path[3 * i + 1] = list[i].move; path[3 * i + 2] = list[i].extra; }
  return count;
}

/* Plays move i of the loaded position on the loaded position. */
void position_step(int game, int i) {
  Move list[MAX_MOVES];
  const Rules *r = rules_of(game);
  r->moves(loaded, list);
  r->apply(loaded, list[i]);
}

int position_score(int game) { return rules_of(game)->score(loaded); }
int position_key_high(int game) { return (int)(rules_of(game)->key(loaded) >> 32); }
int position_key_low(int game) { return (int)(rules_of(game)->key(loaded) & 0xffffffffu); }
