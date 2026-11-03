/* The search of baize.html's C solvers: best first on a score, over a game's own moves, with a table of the
   positions seen. One core, and a Rules table for each game (forty.h, spider.h), so that a better search helps
   every game. No libraries: built with clang --target=wasm32 -nostdlib (see build.sh).

   A game is a state of at most MAX_STATE bytes that packs into at most MAX_PACKED, a list of moves (kind, move and
   extra bytes, which only the game understands), a score (higher is better), a 64-bit position name, and a test
   for a win. The caller writes a position to `image` (its format is the game's: see `load`), calls solve(game, nodes),
   and reads the moves from `path` (three bytes each); the answer is how many, or -1. */

typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;
typedef unsigned long long u64;

#ifndef MAX_NODES
#define MAX_NODES 600000
#endif
#ifndef TABLE_BITS
#define TABLE_BITS 20
#endif
#define MAX_STATE 1024
#define MAX_PACKED 128
#ifndef MAX_EXPANDED
#define MAX_EXPANDED 40000
#endif
#define MAX_PATH 1024

typedef struct { u8 kind, move, extra; } Move;

typedef struct {
  int state_size;
  int (*moves)(const void *g, Move *out);               /* how many; at most MAX_MOVES */
  void (*apply)(void *g, Move m);
  u64 (*key)(const void *g);                            /* never zero */
  int (*score)(const void *g);
  int (*won)(const void *g);
  int (*pack)(const void *g, u8 *out);
  void (*unpack)(const u8 *in, void *g);
  void (*load)(const u8 *image, void *g);               /* any position, from its image */
  const int *defaults;                                  /* the knobs (tuning, from 0) for this game; zeros if short */
} Rules;

#define MAX_MOVES 256

static u64 mix(u64 x) {
  x += 0x9e3779b97f4a7c15ULL;
  x = (x ^ (x >> 30)) * 0xbf58476d1ce4e5b9ULL;
  x = (x ^ (x >> 27)) * 0x94d049bb133111ebULL;
  return x ^ (x >> 31);
}

static void copy(void *to, const void *from, int n) {
  u8 *a = to; const u8 *b = from;
  while (n--) *a++ = *b++;
}

/* Knobs for the search and the scores, which the tests and experiments can set: tuning[0] is the cost of each move
   deeper, tuning[1] the size of the random tie-break (zero: none), tuning[2] its seed. With tuning[3] above zero the
   search restarts every so many positions, taking the cost of depth in turn from tuning[4...7] (until a zero) and
   a new seed each time; the games use the rest. */
int tuning[32];                                  /* each game has its own defaults, which solve() copies here */

/* A position that has been seen is a small record of how it was reached: its state is rebuilt from its parent's,
   which is kept (packed) once the parent has been expanded, so that the memory goes mostly on the positions
   that were looked at and not on all that were found. */
typedef struct { int parent; int score; int slot; u16 depth; u8 kind, move, extra; } Node;
static Node nodes[MAX_NODES];
static u8 packed[MAX_EXPANDED][MAX_PACKED];     /* the states of the expanded positions, by `slot` */
static int heap[MAX_NODES];
static int heap_size, node_count;
static u64 seen[1 << TABLE_BITS];

static const Rules *rules;
static u8 current[MAX_STATE], following[MAX_STATE];

static int better(int a, int b) { return nodes[a].score > nodes[b].score || (nodes[a].score == nodes[b].score && a < b); }

static void push(int id) {
  int i = heap_size++;
  heap[i] = id;
  while (i > 0) {
    int parent = (i - 1) >> 1;
    if (!better(heap[i], heap[parent])) break;
    int t = heap[i]; heap[i] = heap[parent]; heap[parent] = t;
    i = parent;
  }
}

static int pop(void) {
  int best = heap[0];
  heap[0] = heap[--heap_size];
  for (int i = 0;;) {
    int big = i, l = 2 * i + 1, r = 2 * i + 2;
    if (l < heap_size && better(heap[l], heap[big])) big = l;
    if (r < heap_size && better(heap[r], heap[big])) big = r;
    if (big == i) break;
    int t = heap[i]; heap[i] = heap[big]; heap[big] = t;
    i = big;
  }
  return best;
}

/* Is this key new? Claims it if so. */
static int claim(u64 k) {
  u32 i = (u32)(k >> 20) & ((1u << TABLE_BITS) - 1);
  while (seen[i]) { if (seen[i] == k) return 0; i = (i + 1) & ((1u << TABLE_BITS) - 1); }
  seen[i] = k;
  return 1;
}

static int add(const void *g, int parent, Move m) {
  u64 k = rules->key(g);
  if (node_count >= MAX_NODES || !claim(k)) return 0;
  Node *n = &nodes[node_count];
  n->parent = parent; n->kind = m.kind; n->move = m.move; n->extra = m.extra;
  n->depth = parent < 0 ? 0 : nodes[parent].depth + 1;
  n->score = rules->score(g) - tuning[0] * n->depth;
  if (tuning[1]) n->score = n->score * 256 + (int)(mix(k ^ (u64)tuning[2]) % (u64)(tuning[1] * 256)) ; else n->score *= 256;
  push(node_count++);
  return 1;
}

u8 image[256];
u8 path[3 * MAX_PATH];
int expansions;

/* One best-first search from the position in `image`: the number of moves of a winning line (in `path`), or -1. */
static int attempt(const Rules *r, int budget) {
  rules = r;
  for (int i = 0; i < (1 << TABLE_BITS); i++) seen[i] = 0;
  heap_size = node_count = 0;
  int before = expansions;
  budget += before;
  r->load(image, current);
  Move none = { 0, 0, 0 };
  add(current, -1, none);
  while (heap_size && expansions < budget) {
    if (expansions - before >= MAX_EXPANDED) break;
    int id = pop();
    if (id == 0) r->load(image, current);
    else {
      Node *at = &nodes[id];
      r->unpack(packed[nodes[at->parent].slot], current);
      Move m = { at->kind, at->move, at->extra };
      r->apply(current, m);
    }
    nodes[id].slot = expansions - before;
    r->pack(current, packed[nodes[id].slot]);
    expansions++;
    if (r->won(current)) {
      int n = 0;
      for (int at = id; nodes[at].parent >= 0; at = nodes[at].parent) n++;
      if (n > MAX_PATH) return -1;
      int k = n;
      for (int at = id; nodes[at].parent >= 0; at = nodes[at].parent) {
        --k;
        path[3 * k] = nodes[at].kind; path[3 * k + 1] = nodes[at].move; path[3 * k + 2] = nodes[at].extra;
      }
      return n;
    }
    Move list[MAX_MOVES];
    int count = r->moves(current, list);
    for (int i = 0; i < count; i++) {
      copy(following, current, r->state_size);
      r->apply(following, list[i]);
      add(following, id, list[i]);
    }
  }
  return -1;
}

/* The search: attempts, as the knobs say (one with the whole budget, if they say nothing). */
static int search(const Rules *r, int budget) {
  expansions = 0;
  if (tuning[3] <= 0) return attempt(r, budget);
  int cost = tuning[0], seed = tuning[2], costs = 0;
  while (costs < 4 && tuning[4 + costs]) costs++;
  for (int k = 0; expansions < budget; k++) {
    if (costs) tuning[0] = tuning[4 + k % costs];
    tuning[2] = seed + k;
    int left = budget - expansions;
    int found = attempt(r, left < tuning[3] ? left : tuning[3]);
    if (found >= 0) { tuning[0] = cost; tuning[2] = seed; return found; }
  }
  tuning[0] = cost; tuning[2] = seed;
  return -1;
}
