/* Forty Thieves solver for baize.html: the same search as the JavaScript one (best first, on a score), in C
   compiled to WebAssembly. No libraries: it is built with clang --target=wasm32 -nostdlib (see build.sh).

   Cards are bytes: suit * 16 + rank (rank 1 to 13). The caller writes the 104 cards in dealing order to `deck`
   (ten columns of four from the start, and the rest the stock, whose last card is drawn first) and calls
   solve(nodes). The answer is the number of moves in `path` (each move is a byte pair, see below), or -1. */

typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;
typedef unsigned long long u64;

#define COLUMNS 10
#define CAP 24                  /* a column starts with 4 cards and then only grows by one run of at most 13 */
#define HOMES 8
#define MAX_NODES 150000
#define TABLE_BITS 19

enum { DRAW = 0, TO_COLUMN = 1, TO_HOME = 2 };      /* a move is (kind, from * 16 + to), from 10 being the waste */

/* The compiler asks for this when a structure is copied. */
void *memcpy(void *to, const void *from, unsigned long n) {
  u8 *a = to; const u8 *b = from;
  while (n--) *a++ = *b++;
  return to;
}

u8 deck[104];
u8 path[1024];
int expansions;

typedef struct {
  u8 len[COLUMNS];
  u8 col[COLUMNS][CAP];
  u8 waste[64];
  u8 wlen, slen;
  u8 home[HOMES];               /* suit * 16 + top rank, or 0; kept sorted, since the foundations are interchangeable */
} Game;

static u8 stock[64];

typedef struct { u8 data[128]; int parent; int score; u8 kind, move; } Node;
static Node nodes[MAX_NODES];
static int heap[MAX_NODES];
static int heap_size, node_count;
static u64 seen[1 << TABLE_BITS];

/* ---- packing: a node keeps the lengths, the foundations and then the cards of the columns and the waste ---- */

static int pack(const Game *g, u8 *out) {
  int n = 0;
  for (int i = 0; i < COLUMNS; i++) out[n++] = g->len[i];
  out[n++] = g->wlen; out[n++] = g->slen;
  for (int i = 0; i < HOMES; i++) out[n++] = g->home[i];
  for (int i = 0; i < COLUMNS; i++) for (int j = 0; j < g->len[i]; j++) out[n++] = g->col[i][j];
  for (int j = 0; j < g->wlen; j++) out[n++] = g->waste[j];
  return n;
}

static void unpack(const u8 *in, Game *g) {
  int n = 0;
  for (int i = 0; i < COLUMNS; i++) g->len[i] = in[n++];
  g->wlen = in[n++]; g->slen = in[n++];
  for (int i = 0; i < HOMES; i++) g->home[i] = in[n++];
  for (int i = 0; i < COLUMNS; i++) for (int j = 0; j < g->len[i]; j++) g->col[i][j] = in[n++];
  for (int j = 0; j < g->wlen; j++) g->waste[j] = in[n++];
}

/* ---- the position's name and score ---- */

static u64 mix(u64 x) {
  x += 0x9e3779b97f4a7c15ULL;
  x = (x ^ (x >> 30)) * 0xbf58476d1ce4e5b9ULL;
  x = (x ^ (x >> 27)) * 0x94d049bb133111ebULL;
  return x ^ (x >> 31);
}

static u64 key_of(const Game *g) {
  u64 cols[COLUMNS];
  for (int i = 0; i < COLUMNS; i++) {
    u64 h = 0x1234567ULL + g->len[i];
    for (int j = 0; j < g->len[i]; j++) h = mix(h ^ (u64)(g->col[i][j] + 1));
    cols[i] = h;
  }
  for (int i = 1; i < COLUMNS; i++) { u64 v = cols[i]; int j = i - 1; while (j >= 0 && cols[j] > v) { cols[j + 1] = cols[j]; j--; } cols[j + 1] = v; }
  u64 h = mix(g->slen * 131ULL + g->wlen);
  for (int i = 0; i < COLUMNS; i++) h = mix(h ^ cols[i]);
  u64 w = 0x777ULL;
  for (int j = 0; j < g->wlen; j++) w = mix(w ^ (u64)(g->waste[j] + 1));
  h = mix(h ^ w);
  for (int i = 0; i < HOMES; i++) h = mix(h ^ (u64)(g->home[i] + 1000));
  return h | 1;                  /* never zero, which marks an empty slot */
}

static int home_total(const Game *g) {
  int n = 0;
  for (int i = 0; i < HOMES; i++) n += g->home[i] & 15;
  return n;
}

/* Cards home count most; then in-suit links in the columns; empty columns help; cards in the stock cost a little. */
static int score_of(const Game *g) {
  int score = 80 * home_total(g) - g->slen;
  for (int i = 0; i < COLUMNS; i++) {
    if (!g->len[i]) { score += 40; continue; }
    for (int j = 1; j < g->len[i]; j++) {
      u8 below = g->col[i][j - 1], c = g->col[i][j];
      if ((below >> 4) == (c >> 4) && (below & 15) == (c & 15) + 1) score += 16;
    }
  }
  return score;
}

/* ---- moves ---- */

static void sort_homes(Game *g) {
  for (int i = 1; i < HOMES; i++) { u8 v = g->home[i]; int j = i - 1; while (j >= 0 && g->home[j] > v) { g->home[j + 1] = g->home[j]; j--; } g->home[j + 1] = v; }
}

/* The foundation that takes this card, or -1. */
static int home_for(const Game *g, u8 c) {
  int suit = c >> 4, rank = c & 15;
  for (int i = 0; i < HOMES; i++) {
    if (rank == 1 ? g->home[i] == 0 : (g->home[i] >> 4) == suit && (g->home[i] & 15) == rank - 1 && g->home[i]) return i;
  }
  return -1;
}

static int top_of(const Game *g, int from) { return from == COLUMNS ? g->waste[g->wlen - 1] : g->col[from][g->len[from] - 1]; }

static void take(Game *g, int from) { if (from == COLUMNS) g->wlen--; else g->len[from]--; }

typedef struct { u8 kind, move; } Move;

static int moves_of(const Game *g, Move *out) {
  int n = 0;
  for (int from = 0; from <= COLUMNS; from++) {                         /* home first */
    if (from == COLUMNS ? !g->wlen : !g->len[from]) continue;
    if (home_for(g, (u8)top_of(g, from)) >= 0) { out[n].kind = TO_HOME; out[n].move = (u8)(from * 16); n++; }
  }
  for (int from = 0; from <= COLUMNS; from++) {                         /* then column to column */
    if (from == COLUMNS ? !g->wlen : !g->len[from]) continue;
    int c = top_of(g, from), single = from != COLUMNS && g->len[from] == 1, empty_taken = 0;
    for (int to = 0; to < COLUMNS; to++) {
      if (to == from) continue;
      if (g->len[to]) {
        u8 landing = g->col[to][g->len[to] - 1];
        if ((landing >> 4) != (c >> 4) || (landing & 15) != (c & 15) + 1) continue;
      } else {
        if (single || empty_taken) continue;                           /* a lone card gains nothing from a bare column */
        empty_taken = 1;
      }
      out[n].kind = TO_COLUMN; out[n].move = (u8)(from * 16 + to); n++;
    }
  }
  if (g->slen) { out[n].kind = DRAW; out[n].move = 0; n++; }
  return n;
}

static void apply(Game *g, Move m) {
  if (m.kind == DRAW) { g->waste[g->wlen++] = stock[--g->slen]; return; }
  int from = m.move >> 4, to = m.move & 15;
  u8 c = (u8)top_of(g, from);
  take(g, from);
  if (m.kind == TO_HOME) {
    int i = home_for(g, c);
    g->home[i] = c;
    sort_homes(g);
  } else {
    g->col[to][g->len[to]++] = c;
  }
}

/* ---- the search ---- */

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

static int add(const Game *g, int parent, Move m) {
  if (node_count >= MAX_NODES || !claim(key_of(g))) return 0;
  Node *n = &nodes[node_count];
  pack(g, n->data);
  n->parent = parent; n->kind = m.kind; n->move = m.move;
  n->score = score_of(g);
  push(node_count++);
  return 1;
}

int deck_address(void) { return (int)(long)deck; }
int path_address(void) { return (int)(long)path; }
int expansions_done(void) { return expansions; }

int solve(int budget) {
  for (int i = 0; i < (1 << TABLE_BITS); i++) seen[i] = 0;
  heap_size = node_count = expansions = 0;
  Game g;
  for (int i = 0; i < COLUMNS; i++) { g.len[i] = 4; for (int j = 0; j < 4; j++) g.col[i][j] = deck[i * 4 + j]; }
  for (int i = 0; i < 64; i++) stock[i] = deck[40 + i];
  g.slen = 64; g.wlen = 0;
  for (int i = 0; i < HOMES; i++) g.home[i] = 0;
  Move none = { 0, 0 };
  add(&g, -1, none);
  while (heap_size && expansions < budget) {
    int id = pop();
    expansions++;
    Game cur;
    unpack(nodes[id].data, &cur);
    if (home_total(&cur) == 104) {
      int n = 0;
      for (int at = id; nodes[at].parent >= 0; at = nodes[at].parent) n++;
      if (n > (int)sizeof(path) / 2) return -1;
      int k = n;
      for (int at = id; nodes[at].parent >= 0; at = nodes[at].parent) { --k; path[2 * k] = nodes[at].kind; path[2 * k + 1] = nodes[at].move; }
      return n;
    }
    Move list[64];
    int count = moves_of(&cur, list);
    for (int i = 0; i < count; i++) {
      Game next = cur;
      apply(&next, list[i]);
      add(&next, id, list[i]);
    }
  }
  return -1;
}
