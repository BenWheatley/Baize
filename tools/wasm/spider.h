/* Spider rules for the C search (core.h): the same moves, score and position name as the JavaScript ruleset
   (test/engine.test.js compares them). Cards are bytes: suit * 16 + rank (rank 1 to 13), plus 128 when face down.
   The image of a position is the stock count, the finished runs by suit, the ten lengths, then the stock (in
   dealing order: its last card is dealt first) and the columns, as card bytes. */

#define S_COLUMNS 10
#define S_CAP 80                /* the longest column the search will build; the rules have no limit, but this is far past play */

typedef struct {
  u8 len[S_COLUMNS];
  u8 col[S_COLUMNS][S_CAP];
  u8 stock;                     /* cards left in the stock: always a multiple of ten */
  u8 done[4];                   /* finished runs, by suit */
} SGame;

static u8 s_stock[50];
int spider_gaps = 1;            /* may the stock be dealt while a column is empty? (set by the caller) */

enum { S_DEAL = 0, S_MOVE = 1 };     /* a move is (kind, from * 16 + to, cards) */

static int s_up(u8 c) { return !(c & 128); }
static int s_rank(u8 c) { return c & 15; }
static int s_suit(u8 c) { return (c >> 4) & 7; }

/* How many cards at the end of a column are a face-up run of one suit, each one below the last. */
static int s_run(const SGame *g, int i) {
  int n = g->len[i], k = 0;
  while (k < n) {
    u8 c = g->col[i][n - 1 - k];
    if (!s_up(c)) break;
    if (k && !(s_suit(g->col[i][n - k]) == s_suit(c) && s_rank(g->col[i][n - k]) == s_rank(c) - 1)) break;
    k++;
  }
  return k;
}

static int s_can_deal(const SGame *g) {
  if (g->stock < S_COLUMNS) return 0;
  for (int i = 0; i < S_COLUMNS; i++) {
    if (!g->len[i] && !spider_gaps) return 0;
    if (g->len[i] >= S_CAP) return 0;
  }
  return 1;
}

/* Moves that build within a suit first, then those that turn a card over, then the rest; the deal last. */
static int s_moves(const void *p, Move *out) {
  const SGame *g = p;
  Move flips[MAX_MOVES], others[MAX_MOVES];
  int nbest = 0, nflips = 0, nothers = 0;
  for (int from = 0; from < S_COLUMNS; from++) {
    int n = g->len[from], m = s_run(g, from);
    for (int index = n - 1; index >= n - m; index--) {
      u8 lead = g->col[from][index];
      int spare = 0, count = n - index;
      for (int to = 0; to < S_COLUMNS; to++) {
        if (to == from || g->len[to] + count > S_CAP) continue;
        int empty = !g->len[to];
        if (empty) {
          if (index == 0 || spare) continue;
          spare = 1;
        } else {
          u8 landing = g->col[to][g->len[to] - 1];
          if (s_rank(landing) != s_rank(lead) + 1) continue;
        }
        Move move = { S_MOVE, (u8)(from * 16 + to), (u8)count };
        if (!empty && s_suit(g->col[to][g->len[to] - 1]) == s_suit(lead)) out[nbest++] = move;
        else if (index > 0 && !s_up(g->col[from][index - 1])) flips[nflips++] = move;
        else others[nothers++] = move;
      }
    }
  }
  for (int i = 0; i < nflips; i++) out[nbest + i] = flips[i];
  for (int i = 0; i < nothers; i++) out[nbest + nflips + i] = others[i];
  int total = nbest + nflips + nothers;
  if (s_can_deal(g)) { Move deal = { S_DEAL, 0, 0 }; out[total++] = deal; }
  return total;
}

/* A finished run (king to ace of one suit, face up) leaves the table, and the card beneath turns up. */
static void s_clear_runs(SGame *g) {
  for (int i = 0; i < S_COLUMNS; i++) {
    int n = g->len[i];
    if (n < 13 || s_rank(g->col[i][n - 13]) != 13) continue;
    int whole = 1;
    for (int j = n - 13; j < n && whole; j++) {
      u8 c = g->col[i][j];
      whole = s_up(c) && s_suit(c) == s_suit(g->col[i][n - 13]) && s_rank(c) == 13 - (j - (n - 13));
    }
    if (!whole) continue;
    g->done[s_suit(g->col[i][n - 13])]++;
    g->len[i] = n - 13;
    if (g->len[i]) g->col[i][g->len[i] - 1] &= 127;
  }
}

static void s_apply(void *p, Move m) {
  SGame *g = p;
  if (m.kind == S_DEAL) {
    for (int i = 0; i < S_COLUMNS; i++) g->col[i][g->len[i]++] = s_stock[--g->stock];
  } else {
    int from = m.move >> 4, to = m.move & 15, count = m.extra;
    for (int j = 0; j < count; j++) g->col[to][g->len[to]++] = g->col[from][g->len[from] - count + j];
    g->len[from] -= count;
    if (g->len[from]) g->col[from][g->len[from] - 1] &= 127;
  }
  s_clear_runs(g);
}

/* The columns are interchangeable, the finished runs only count, and cards of one suit and rank are alike. */
static u64 s_key(const void *p) {
  const SGame *g = p;
  u64 cols[S_COLUMNS];
  for (int i = 0; i < S_COLUMNS; i++) {
    u64 h = 0x7654321ULL + g->len[i];
    for (int j = 0; j < g->len[i]; j++) h = mix(h ^ (u64)(g->col[i][j] + 1));
    cols[i] = h;
  }
  for (int i = 1; i < S_COLUMNS; i++) { u64 v = cols[i]; int j = i - 1; while (j >= 0 && cols[j] > v) { cols[j + 1] = cols[j]; j--; } cols[j + 1] = v; }
  u64 h = mix(g->stock * 977ULL + 1);
  for (int i = 0; i < S_COLUMNS; i++) h = mix(h ^ cols[i]);
  for (int i = 0; i < 4; i++) h = mix(h ^ (u64)(g->done[i] + 5000 * (i + 1)));
  return h | 1;
}

/* Finished runs count most; then one-suit links, empty columns and turned-over cards; a smaller card under a bigger
   one costs a little, and so does each card left in the stock. Ten times the JavaScript score. The weights are
   tuning[8...]: run, empty column, face down, link, stock card, buried (a smaller card under a bigger one),
   the extra for a longer run, a king at the bottom of a column, a different-suit descending pair. */
enum { W_RUN = 8, W_EMPTY, W_DOWN, W_LINK, W_STOCK, W_BURY, W_LONG, W_KING, W_MIXED };

static int s_score(const void *p) {
  const SGame *g = p;
  int score = -g->stock * tuning[W_STOCK];
  for (int i = 0; i < 4; i++) score += tuning[W_RUN] * g->done[i];
  for (int i = 0; i < S_COLUMNS; i++) {
    if (!g->len[i]) { score += tuning[W_EMPTY]; continue; }
    int run = 0;
    for (int j = 0; j < g->len[i]; j++) {
      u8 c = g->col[i][j];
      if (!s_up(c)) { score -= tuning[W_DOWN]; run = 0; continue; }
      if (!j) { if (s_rank(c) == 13) score += tuning[W_KING]; run = 0; continue; }
      u8 below = g->col[i][j - 1];
      if (!s_up(below)) { run = 0; continue; }
      if (s_rank(below) == s_rank(c) + 1) {
        if (s_suit(below) == s_suit(c)) { score += tuning[W_LINK] + tuning[W_LONG] * run; run++; }
        else { score += tuning[W_MIXED]; run = 0; }
      } else {
        run = 0;
        if (s_rank(below) < s_rank(c)) score -= tuning[W_BURY];
      }
    }
  }
  return score;
}

static int s_won(const void *p) {
  const SGame *g = p;
  return g->done[0] + g->done[1] + g->done[2] + g->done[3] == 8;
}

/* A node keeps the stock, the finished runs, the lengths and then the cards. */
static int s_pack(const void *p, u8 *out) {
  const SGame *g = p;
  int n = 0;
  out[n++] = g->stock;
  for (int i = 0; i < 4; i++) out[n++] = g->done[i];
  for (int i = 0; i < S_COLUMNS; i++) out[n++] = g->len[i];
  for (int i = 0; i < S_COLUMNS; i++) for (int j = 0; j < g->len[i]; j++) out[n++] = g->col[i][j];
  return n;
}

static void s_unpack(const u8 *in, void *p) {
  SGame *g = p;
  int n = 0;
  g->stock = in[n++];
  for (int i = 0; i < 4; i++) g->done[i] = in[n++];
  for (int i = 0; i < S_COLUMNS; i++) g->len[i] = in[n++];
  for (int i = 0; i < S_COLUMNS; i++) for (int j = 0; j < g->len[i]; j++) g->col[i][j] = in[n++];
}

static void s_load(const u8 *image, void *p) {
  SGame *g = p;
  int n = 0;
  g->stock = image[n++];
  for (int i = 0; i < 4; i++) g->done[i] = image[n++];
  for (int i = 0; i < S_COLUMNS; i++) g->len[i] = image[n++];
  for (int j = 0; j < g->stock; j++) s_stock[j] = image[n++];
  for (int i = 0; i < S_COLUMNS; i++) for (int j = 0; j < g->len[i]; j++) g->col[i][j] = image[n++];
}

/* What works best, by measurement (docs/spider-four-suits.md): each attempt costs a move deeper 40 to 60 units,
   with a little random tie-breaking, and is dropped after 30000 positions for another. */
static const int spider_defaults[32] = { 60, 10, 0, 30000, 40, 50, 60, 50,
  1000, 60, 80, 80, 1, 30, 0, 0, 0 };            /* from 8: the weights of the score above */

static const Rules spider_rules = { sizeof(SGame), s_moves, s_apply, s_key, s_score, s_won, s_pack, s_unpack, s_load, spider_defaults };
