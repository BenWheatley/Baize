/* Forty Thieves rules for the C search (core.h): the same moves, score and position name as the JavaScript ruleset
   (test/engine.test.js compares them). Cards are bytes: suit * 16 + rank (rank 1 to 13). The deck is the 104 cards
   in dealing order: ten columns of four from the start, and the rest the f_stock, whose last card is drawn first. */

#define F_COLUMNS 10
#define F_CAP 24                  /* a column starts with 4 cards and then only grows by one run of at most 13 */
#define F_HOMES 8

enum { F_DRAW = 0, F_TO_COLUMN = 1, F_TO_HOME = 2 };      /* a move is (kind, from * 16 + to), from 10 being the waste */

typedef struct {
  u8 len[F_COLUMNS];
  u8 col[F_COLUMNS][F_CAP];
  u8 waste[64];
  u8 wlen, slen;
  u8 home[F_HOMES];               /* suit * 16 + top rank, or 0; kept sorted, since the foundations are interchangeable */
} FGame;

static u8 f_stock[64];

/* ---- packing: a node keeps the lengths, the foundations and then the cards of the columns and the waste ---- */

static int f_pack(const FGame *g, u8 *out) {
  int n = 0;
  for (int i = 0; i < F_COLUMNS; i++) out[n++] = g->len[i];
  out[n++] = g->wlen; out[n++] = g->slen;
  for (int i = 0; i < F_HOMES; i++) out[n++] = g->home[i];
  for (int i = 0; i < F_COLUMNS; i++) for (int j = 0; j < g->len[i]; j++) out[n++] = g->col[i][j];
  for (int j = 0; j < g->wlen; j++) out[n++] = g->waste[j];
  return n;
}

static void f_unpack(const u8 *in, FGame *g) {
  int n = 0;
  for (int i = 0; i < F_COLUMNS; i++) g->len[i] = in[n++];
  g->wlen = in[n++]; g->slen = in[n++];
  for (int i = 0; i < F_HOMES; i++) g->home[i] = in[n++];
  for (int i = 0; i < F_COLUMNS; i++) for (int j = 0; j < g->len[i]; j++) g->col[i][j] = in[n++];
  for (int j = 0; j < g->wlen; j++) g->waste[j] = in[n++];
}

/* ---- the position's name and score ---- */


static u64 f_key(const FGame *g) {
  u64 cols[F_COLUMNS];
  for (int i = 0; i < F_COLUMNS; i++) {
    u64 h = 0x1234567ULL + g->len[i];
    for (int j = 0; j < g->len[i]; j++) h = mix(h ^ (u64)(g->col[i][j] + 1));
    cols[i] = h;
  }
  for (int i = 1; i < F_COLUMNS; i++) { u64 v = cols[i]; int j = i - 1; while (j >= 0 && cols[j] > v) { cols[j + 1] = cols[j]; j--; } cols[j + 1] = v; }
  u64 h = mix(g->slen * 131ULL + g->wlen);
  for (int i = 0; i < F_COLUMNS; i++) h = mix(h ^ cols[i]);
  u64 w = 0x777ULL;
  for (int j = 0; j < g->wlen; j++) w = mix(w ^ (u64)(g->waste[j] + 1));
  h = mix(h ^ w);
  for (int i = 0; i < F_HOMES; i++) h = mix(h ^ (u64)(g->home[i] + 1000));
  return h | 1;                  /* never zero, which marks an empty slot */
}

static int f_home_total(const FGame *g) {
  int n = 0;
  for (int i = 0; i < F_HOMES; i++) n += g->home[i] & 15;
  return n;
}

/* Cards home count most; then in-suit links in the columns; empty columns help; cards in the f_stock cost a little. */
static int f_score(const FGame *g) {
  int score = 80 * f_home_total(g) - g->slen;
  for (int i = 0; i < F_COLUMNS; i++) {
    if (!g->len[i]) { score += 40; continue; }
    for (int j = 1; j < g->len[i]; j++) {
      u8 below = g->col[i][j - 1], c = g->col[i][j];
      if ((below >> 4) == (c >> 4) && (below & 15) == (c & 15) + 1) score += 16;
    }
  }
  return score;
}

/* ---- moves ---- */

static void f_sort_homes(FGame *g) {
  for (int i = 1; i < F_HOMES; i++) { u8 v = g->home[i]; int j = i - 1; while (j >= 0 && g->home[j] > v) { g->home[j + 1] = g->home[j]; j--; } g->home[j + 1] = v; }
}

/* The foundation that takes this card, or -1. */
static int f_home_for(const FGame *g, u8 c) {
  int suit = c >> 4, rank = c & 15;
  for (int i = 0; i < F_HOMES; i++) {
    if (rank == 1 ? g->home[i] == 0 : (g->home[i] >> 4) == suit && (g->home[i] & 15) == rank - 1 && g->home[i]) return i;
  }
  return -1;
}

static int f_top(const FGame *g, int from) { return from == F_COLUMNS ? g->waste[g->wlen - 1] : g->col[from][g->len[from] - 1]; }

static void f_take(FGame *g, int from) { if (from == F_COLUMNS) g->wlen--; else g->len[from]--; }


static int f_moves(const FGame *g, Move *out) {
  int n = 0;
  for (int from = 0; from <= F_COLUMNS; from++) {                         /* home first */
    if (from == F_COLUMNS ? !g->wlen : !g->len[from]) continue;
    if (f_home_for(g, (u8)f_top(g, from)) >= 0) { out[n].kind = F_TO_HOME; out[n].move = (u8)(from * 16); n++; }
  }
  for (int from = 0; from <= F_COLUMNS; from++) {                         /* then column to column */
    if (from == F_COLUMNS ? !g->wlen : !g->len[from]) continue;
    int c = f_top(g, from), single = from != F_COLUMNS && g->len[from] == 1, empty_taken = 0;
    for (int to = 0; to < F_COLUMNS; to++) {
      if (to == from) continue;
      if (g->len[to]) {
        u8 landing = g->col[to][g->len[to] - 1];
        if ((landing >> 4) != (c >> 4) || (landing & 15) != (c & 15) + 1) continue;
      } else {
        if (single || empty_taken) continue;                           /* a lone card gains nothing from a bare column */
        empty_taken = 1;
      }
      out[n].kind = F_TO_COLUMN; out[n].move = (u8)(from * 16 + to); n++;
    }
  }
  if (g->slen) { out[n].kind = F_DRAW; out[n].move = 0; n++; }
  return n;
}

static void f_apply(FGame *g, Move m) {
  if (m.kind == F_DRAW) { g->waste[g->wlen++] = f_stock[--g->slen]; return; }
  int from = m.move >> 4, to = m.move & 15;
  u8 c = (u8)f_top(g, from);
  f_take(g, from);
  if (m.kind == F_TO_HOME) {
    int i = f_home_for(g, c);
    g->home[i] = c;
    f_sort_homes(g);
  } else {
    g->col[to][g->len[to]++] = c;
  }
}


/* ---- the interface of core.h ---- */

static int forty_moves(const void *p, Move *out) {
  int n = f_moves(p, out);
  for (int i = 0; i < n; i++) out[i].extra = 0;
  return n;
}
static void forty_apply(void *p, Move m) { f_apply(p, m); }
static u64 forty_key(const void *p) { return f_key(p); }
static int forty_score(const void *p) { return f_score(p); }
static int forty_won(const void *p) { return f_home_total(p) == 104; }
static int forty_pack(const void *p, u8 *out) { return f_pack(p, out); }
static void forty_unpack(const u8 *in, void *p) { f_unpack(in, p); }

static void forty_load(const u8 *image, void *p) {
  FGame *g = p;
  int n = 0;
  for (int i = 0; i < F_COLUMNS; i++) g->len[i] = image[n++];
  g->wlen = image[n++]; g->slen = image[n++];
  for (int i = 0; i < F_HOMES; i++) g->home[i] = image[n++];
  f_sort_homes(g);
  for (int j = 0; j < g->slen; j++) f_stock[j] = image[n++];
  for (int i = 0; i < F_COLUMNS; i++) for (int j = 0; j < g->len[i]; j++) g->col[i][j] = image[n++];
  for (int j = 0; j < g->wlen; j++) g->waste[j] = image[n++];
}

static const int forty_defaults[32] = { 0 };               /* one search, no depth cost, no weights */

static const Rules forty_rules = { sizeof(FGame), forty_moves, forty_apply, forty_key, forty_score, forty_won, forty_pack, forty_unpack, forty_load, forty_defaults };
