# Finding wins in four-suit Spider by restarting a weighted best-first search

*Baize, November 2026. A working note on how `Deals: Winnable` was made to work for Spider with four suits, with the measurements behind each choice. Everything here can be re-run: see Reproduction.*

## Summary

Given a Spider deal with every card visible (the face-down cards included), the aim is to find a line of play that wins it, within about a second, in a browser. A plain best-first search on a hand-written score wins almost no four-suit deals (1 of 60 within 150,000 positions). Three changes took it to 43 of 60 on deals that were never used for tuning:

1. **A cost for depth** (a weighted A\*-like ordering): 1 → 15 of 60.
2. **A little random tie-breaking, and restarting** the search every 30,000 positions with a different depth cost and tie-break seed: 15 → 43 of 60.
3. **Naming positions up to symmetry** (columns in any order, finished runs only counted) and a score that knows the game, which are what made one and two suits easy and are assumed in the numbers above.

The first of these is a single number that sits just below a cliff. The second exploits a property the searches show clearly: what one setting cannot solve, another often can, and spending the same positions on several short, different attempts beats one long one. I found no published account of either for Spider; that is a statement about what I searched for (below), not a claim of novelty.

The search is in C compiled to WebAssembly (`tools/wasm`). It finds a four-suit winnable deal in about 1.5 s on average on the development machine (a cloud container; a phone will be slower), and one- and two-suit deals in under a quarter of a second.

## 1. The problem

Rules used (those of the game in `baize.html`): ten columns, 54 cards dealt (the last of each column face up), 50 in the stock dealt ten at a time; a card goes on any card one rank higher, but only a face-up run of one suit moves as a unit; a king-to-ace run of one suit leaves the table. Dealing into empty columns is allowed (the `gaps` option, on by default). The search sees the face-down cards, so this is the 'thoughtful' variant of the literature: it measures what can be won with perfect information, which is more than a player can usually do.

A deal counts as *won by the search* only if the search returns a line that the game's own JavaScript rules replay to a win. A deal the search fails on is not thereby shown unwinnable.

## 2. Prior work, and its limits

The standard reference for general solvers is Blake and Gent's study of Solvitaire, a C++ depth-first search with a transposition table, symmetry reduction, dominance rules and 'streamliners', applied to Klondike and many other games including Spider.[^1] Its authors note that for games where nearly every deal is winnable, such as Spider, it spends its effort on proving deals unwinnable rather than on finding wins quickly,[^1] which is the opposite of what this application needs. Its Spider results are reported for one variant only, without a breakdown by number of suits in the text I could read, and I found no runtime figures for four suits. Popular sites quote that more than 99% of four-suit deals are winnable with perfect play,[^2] without naming a method or a sample; I treat that as unverified.

Two older ideas carry over directly, and I did not invent either: weighting depth in best-first search (Pohl's weighted heuristic search),[^3] and restarting a randomised search to avoid heavy-tailed run times (Gomes and others, for satisfiability and constraint problems).[^4]

I did not read the Solvitaire source (the repository was not reachable from my environment), did not search the Spider-specific literature or forums beyond a handful of queries, and cannot rule out earlier work.

## 3. Method

**The search.** Best first on `f = score(position) − c × depth`, where `depth` is the number of moves from the start and `c` the *depth cost*. A table of 64-bit position names (hashes) discards repeated positions. A position's name ignores the order of the columns, counts finished runs per suit instead of recording where they went, and treats the two copies of a card as the same card.

**The score** (the C figures, in tenths of the JavaScript ones; the two are tested to agree): 1000 for each finished run; 80 for each *link* (a card directly on the next-higher card of its suit); 60 for each empty column; −80 for each face-down card; −30 where a smaller card lies directly under a bigger one; −1 for each card still in the stock. Dealing is the last move offered, and moves that build a link are offered first.

**Restarts.** The search runs as a series of attempts of at most 30,000 positions each. Attempt *k* uses depth cost 40, 50, 60, 50, 40, … (in turn) and a random tie-break of up to 10 units (one JavaScript score unit) on the score, seeded by *k*; the first attempt's tie-break is therefore already random. The total budget (150,000 positions in the app) is a prefix of the same sequence, so a larger budget only adds attempts. This keeps the search deterministic and monotone in the budget, which the app relies on so that a hint always agrees with the search that found the deal.

**Memory.** A position seen but not yet expanded is kept as a 16-byte record (parent, move, score); its cards are rebuilt from the parent's, which is stored once the parent has been expanded. This cut a four-suit attempt from about 70 MB to about 12 MB, and the whole module fits in 32 MB. It does not change which positions are searched (checked: identical expansion counts before and after).

## 4. Experiments

All counts are of deals won out of those tried. 'Positions' are expansions of the search. Seeds select the deal (`mulberry32`). Three disjoint sets were used: *tuning* (seeds 100–159), *held out* (1000–1059), which no setting was chosen on, and the earliest JavaScript measurements (seeds 0–29, 100–139). The machine ran roughly 120,000 to 190,000 positions a second in C (it varies with the game and the suits) and about 5,000 in JavaScript.

### 4.1 The starting point

| Search | 1 suit | 2 suits | 4 suits |
|---|---|---|---|
| JavaScript, best-first, no symmetry, 3,000 positions (30 / 30 / 20 deals) | 7 | 1 | 0 |
| + symmetric position name, tuned score (40 unseen deals) | 39 | 9 | 0 |
| C, same score, 150,000 positions (40 / 40 / 10 deals) | 40 | 20 | 0 |
| C, same score, 1,000,000 positions (– / 20 / 6 deals; the experimental build stopped at a million stored positions) | – | 11 | 0 |

More positions did not help beyond a point: two suits solved 50% at 150,000 and 55% at a million. The search was not short of time; it was lost.

### 4.2 The cost of depth

Two suits, 20,000 positions, 40 deals (tuning seeds); the depth cost is the score charged for each move (a link is worth 80, a finished run 1000):

| Depth cost | 0 | 10 | 20 | 30 | 40 | 60 | 70 | 80 | 90 | 100 |
|---|---|---|---|---|---|---|---|---|---|---|
| Deals won | 13 | 19 | 26 | 25 | 32 | 35 | 35 | 26 | 19 | 3 |

Four suits, 150,000 positions, 40 deals: costs 40, 50, 60 and 70 won 16, 16, 22 and 6; cost 80 won 0 of 10.

The pattern is a rise to a broad optimum and then a cliff. My reading, which the numbers fit but do not prove: a typical step of progress creates one link and so gains 80; once the depth cost reaches that, such a step gains nothing, the ordering no longer prefers progress to idling, and the search degrades towards breadth-first. Two scoring changes support this. Setting the link weight to 60 (equal to the cost) won 0 of 60. Setting it to 110 also won 0 of 60, which the same reading explains differently: a finished run removes its twelve links from the board, so with the run worth 1000 and links worth 110 a completed run *lowers* the score and the search never finishes one. Raising the run weight to 2,500 with links at 110 won 14 of 60, better but still below the 23 of the defaults. So the run weight must exceed twelve links, and the balance of the other weights matters too.

### 4.3 Other weights

On four suits (50,000 positions, 60 deals, baseline 23) varying the weight of an empty column, a face-down card, a buried card, a king at the bottom of a column, a different-suit descending pair, the stock, or an extra reward for longer runs moved the result between 10 and 28, mostly within what 60 deals can distinguish (about ±6). A reward for long runs, a king at the bottom, and a smaller empty-column weight were mildly positive but not significantly; I did not keep them. The first is the one I would try again, on a larger sample. After the depth cost, the score's weights are on a plateau.

### 4.4 Diversity and restarts

The decisive observation was in the failures. With six different settings (depth costs 40, 60, 70; tie-break seeds 1, 2, 3), each solving between 6 and 22 of the same 40 deals, the *union* solved 37. The deals one setting cannot solve are not intrinsically hard; they are hard for that ordering. Restarts exploit this directly.

Four suits, 60 tuning deals, total budget, attempts of 30,000 positions with depth costs cycling 40, 50, 60, 50:

| Total positions | 100,000 | 300,000 | 1,000,000 |
|---|---|---|---|
| Deals won | 42 | 50 | 57 |
| Time a deal (average, over all 60) | 1.2 s | 1.4 s | 2.1 s |

At 150,000 positions on the same 60 deals the defaults won 46. Attempt lengths of 15,000 and 50,000 won 45 and 46; tie-breaks of 3 and 30 won 38 and 42; the depth-cost schedule 50, 60, 70, 60 won 39. Only the attempt length is clearly indifferent; the others are no better than the defaults, though most of the gaps are within the noise of 60 deals. I took the defaults and stopped.

### 4.5 Held-out result

Deals 1000–1059, 150,000 positions, the shipped module:

| | 1 suit | 2 suits | 4 suits |
|---|---|---|---|
| Plain best-first, no depth cost, no restarts | – | 29 | 1 |
| + depth cost, tie-break, one attempt | – | 56 | 15 |
| + restarts (shipped) | **60** | **59** | **43** |
| Time to win (median) | 11 ms | 23 ms | 544 ms |
| Time a deal, including failures | 0.02 s | 0.13 s | 1.06 s |
| Time a *win*, including the failures before it | 0.02 s | 0.13 s | 1.48 s |

On the tuning deals the shipped settings won 46 of 60 four-suit deals; the held-out figure of 43 (72%) is the one to quote. The gap, three deals, is within chance, so I see no sign of over-fitting to the tuning set, but the tuning set was small.

## 5. Limits

- **Not a proof.** 28% of four-suit deals went unsolved within the budget; Blake and Gent expect almost all unresolved Spider deals to be winnable,[^1] but this work does not show it. A larger budget wins more (95% of tuning deals at a million positions), so for the unsolved deals the question is time, not (as far as I can tell) existence.
- **Perfect information.** The search reads the face-down cards. The result says nothing about what can be won blind.
- **Rule variants.** With `gaps` off (no dealing into an empty column) deals are harder; it is covered by the correctness tests but not by these rates.
- **One machine, small samples.** Sixty deals per cell; differences of under about six are noise. Times will differ on other hardware; WebAssembly engines vary.
- **Generality.** Nothing here is Spider-specific except the score and the position name. The same core runs Forty Thieves with no restarts and no depth cost, which is its tuned setting.

## 6. What is in the code

`tools/wasm/core.h` holds the search (attempts, table, lazy records); `spider.h` and `forty.h` hold each game's rules, score and position name; `solver.c` is the module's interface; `build.sh` builds it and `embed.py` places it in `baize.html`. Because the C repeats the game's rules, `test/engine.test.js` compares it with the JavaScript rules over random playouts (moves, order, score, position names, and the result of every move; 4,680 Spider positions with one, two and four suits and with dealing into gaps on and off) and replays every line the C returns through the JavaScript rules before the page trusts it. Where WebAssembly is unavailable, one- and two-suit deals are searched by the JavaScript search; four suits are not, and the app says so and deals a random game.

## 7. Reproduction

```
tools/wasm/build.sh && python3 tools/wasm/embed.py
node tools/wasm/measure.js 4 150000 60 1000                         # the shipped settings, held-out deals
node tools/wasm/measure.js 4 150000 60 1000 '{"0":0,"1":0,"3":0}'  # no depth cost, no tie-break, no restarts
node tools/wasm/measure.js 2 20000 40 100 '{"0":60}' '{"0":100}'   # depth cost, in tenths of a link
```

The knob numbers are the indices of `tuning` in `core.h` and `spider.h` (0: depth cost; 1: tie-break size; 2: its seed; 3: attempt length, 0 for a single attempt; 4–7: the depth costs to cycle through; 8 onwards: the score's weights).

## 8. Open questions

- Is the cliff of §4.2 tied to the link weight, as argued, or to the score's overall scale? Rescaling every weight together would tell.
- Learning the weights (or a value function) from solved deals, instead of setting them by hand and sweeping, would be a fairer test of what the score can do.
- Dominance rules ('moves that never hurt', as in Solvitaire) were not tried; they would prune before the search rather than order it.
- Hints from the middle of a game run through the same search; their success rate has not been measured separately.

[^1]: Charlie Blake and Ian P. Gent, 'The Winnability of Klondike Solitaire and Many Other Patience Games', arXiv:1906.12314 <https://arxiv.org/abs/1906.12314> [accessed 2 November 2026]. Read through its HTML and PDF renderings: I could not extract its Spider tables.
[^2]: Spider Solitaire odds page, <https://www.spidersolitaire.to/odds> [accessed 2 November 2026]; it names no method or sample.
[^3]: Ira Pohl, 'Heuristic Search Viewed as Path Finding in a Graph', *Artificial Intelligence*, 1 (1970), 193–204. Cited from memory.
[^4]: Carla P. Gomes, Bart Selman, Nuno Crato and Henry Kautz, 'Heavy-Tailed Phenomena in Satisfiability and Constraint Satisfaction Problems', *Journal of Automated Reasoning*, 24 (2000), 67–100 <https://www.cs.cornell.edu/gomes/pdf/2000_gomes_jar_phenomena.pdf> [accessed 2 November 2026]. I confirmed that the paper exists at this address; I did not re-read it for this note.
