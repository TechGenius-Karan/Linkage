# Linkage — Generation Engine

> Section 7 of [`../planning.md`](../planning.md), split out because nothing
> outside `engine/` reads it. Numbering is preserved: §7.4 here is §7.4 everywhere.

---

## 7. Deep Dive — Python Generation Engine

### 7.1 Vocabulary Construction

**Source:** the `wordfreq` package — `top_n_list('en', VOCAB_FETCH_N)` where `VOCAB_FETCH_N = 12000`, then filtered down to `VOCAB_TARGET = 8000` surviving words.

> Two distinct constants on purpose. `VOCAB_FETCH_N` is how many frequency-ranked words we pull; `VOCAB_TARGET` is how many survive the filter chain. Conflating them makes §7.9 Tier 4 ("widen the vocabulary") ambiguous about which number to raise — the answer is **both**, keeping roughly the same ratio.

Why `wordfreq` over a scraped list: it is frequency-ranked, deterministic for a pinned version, and a single dependency.

> ⚠️ **Pin `wordfreq` exactly.** Its bundled frequency data changes between releases, which would silently change the vocabulary and therefore every puzzle. Record the pinned version in the graph metadata.

Filter chain, in order:

- [ ] Drop stopwords and function words (`the`, `of`, `and`, `is`) — never make an interesting link.
- [ ] Apply the §3.1.1 normalisation rules: lowercase, ASCII `[a-z]` only, 3–12 characters, **no multiword** (anything containing `_`).
- [ ] Drop non-alphabetic tokens (numerals, hyphenates, contractions).
- [ ] Drop profanity and slurs (curated blocklist — this ships to the public).
- [ ] Drop proper nouns *except* a curated allowlist of high-recognition concepts (`newton`, `einstein`, `rome`) — these are where the best "aha" moments live, so we keep them deliberately rather than losing them to a blanket rule.
- [ ] **Restrict to nouns and concrete adjectives** via WordNet POS lookup. Mixed part-of-speech chains (`apple → red → running → fast`) read as incoherent; noun-dominant chains read as thought.

### 7.2 Graph Construction

**Source:** ConceptNet 5.7 assertions dump (`conceptnet-assertions-5.7.0.csv.gz`, ~1.2 GB compressed). Stream-parsed line by line — never loaded into memory whole.

Each line is tab-separated: `uri | relation | start | end | metadata-json`. We keep an edge only when **all** of these hold:

- Both `start` and `end` match `/c/en/<word>` and `<word>` is in the vocabulary.
- The relation is on the whitelist.
- `weight >= 1.0`.

**Relation whitelist** — associations that produce a genuine conceptual leap:

```
RelatedTo    IsA        PartOf       HasA         UsedFor
CapableOf    AtLocation Causes       HasProperty  MadeOf
SymbolOf     MotivatedByGoal
```

**Relation blocklist** — and *why* each is excluded, because this is where puzzle quality is won or lost:

| Excluded | Reason |
|---|---|
| `FormOf`, `DerivedFrom`, `EtymologicallyRelatedTo` | Morphological, not conceptual. `run → running` is not an "aha", it is a suffix. |
| `Synonym`, `SimilarTo` | The leap is too small. Zero insight. |
| `Antonym`, `DistinctFrom` | Reads as a mistake to the player, not a connection. |
| `NotUsedFor`, `NotCapableOf`, `NotHasProperty` | Negations invert the semantics of the whole chain. |
| `ExternalURL`, `dbpedia/*` | Not conceptual data at all. |

**Graph object:** an undirected `networkx.Graph` (the spec's "bidirectional graph"). Edge attribute `weight` (max across sources when a pair appears via multiple relations) and `relations` (the set, kept for `meta` and for debugging bad puzzles).

> ⚠️ **NetworkX 3.x gotcha.** `nx.write_gpickle` / `nx.read_gpickle` were **removed in NetworkX 3.0**. Use `pickle.dump(G, f, protocol=5)` directly; keep the `.gpickle` filename for continuity. Store `{conceptnet_sha256, wordfreq_version, networkx_version, built_at}` as a graph attribute so a mismatched cache is detected rather than silently used.

### 7.3 The Hub-Word Problem

The single largest threat to puzzle quality, and it must be solved at graph-build time.

Words like `thing`, `person`, `make`, `use`, `good`, `time` have enormous degree in ConceptNet. Left in, **every** shortest path routes through them, producing chains like `cat → animal → thing → object → box` — technically valid, completely worthless.

**Mitigation — a curated blocklist, not a degree threshold** *(decided, Phase 1)*:

- [x] **`GENERIC_HUBS`** in `domain/wordlists.py` — a hand-maintained list of words that are generic rather than merely well-connected, applied at the **vocabulary** stage, before the graph is built.
- [x] **Automatic degree pruning is disabled** (`HUB_PERCENTILE = None`).
- [ ] Prefer mid-frequency vocabulary: rank 500–8000. The top 500 are too generic to surprise; below 8000 is too obscure to be fair.
- [ ] After each build, `build-graph` prints the **40 highest-degree words** as candidates for the curated list. Information for a person, not automation.

**Why the threshold lost.** Phase 1 measured it: at P99 it deleted 75 words at `degree > 82` — `animal, art, attack, ball, bar, base, bed, bill, bird, box, break, bridge`. Every one of those is a good puzzle word.

> **Degree measures how *connected* a word is. What ruins a puzzle is how *generic* it is. Those are different properties, and only the second one matters.**
>
> `bird` is connected to everything because birds genuinely relate to flight, eggs, song, feathers and dinosaurs. `thing` is connected to everything because it means nothing in particular. One is rich, one is empty — and a degree count sees two large numbers. A person sees the difference instantly.

The top 40 by degree in the shipped graph — `animal, device, building, horse, plate, plant, table, tree, bar, space, ground, ball, land, field, town, metal, box, rock, bed, fish, church, capital, ring, cabinet, ship, wood` — is a list of *good tiles*. That is the clearest possible evidence this signal was never the right one to prune on. Genuinely empty words are few and abstract, and are already on the curated list.

Keeping the ranking as a **report** preserves the useful half of the idea (§7.9.4 Tier 3): it is exactly the right shortlist to review by hand when deciding what to add to `GENERIC_HUBS`. The pruning machinery stays in the codebase and stays tested, so re-enabling it is a one-line config change if the curated list ever proves insufficient.

### 7.4 Pathfinding — Bidirectional Bounded BFS

We need paths of **exactly 5 edges** (6 nodes: `S → w1 → w2 → w3 → w4 → E`). Naive BFS from `S` to depth 5 explodes in a graph this dense; meeting in the middle does not.

```
        S ---> w1 ---> w2        w3 <--- w4 <--- E
        |______________|          |______________|
         forward BFS, depth 2     backward BFS, depth 2
                        \        /
                         bridge edge (w2, w3)
```

Algorithm:

1. `F` = every node at distance **exactly 2** from `S`, each with its path.
2. `B` = every node at distance **exactly 2** from `E`, each with its path.
3. For every edge `(u, v)` with `u ∈ F` and `v ∈ B`: emit `S → u.path → v.path(reversed) → E`.

Frontier expansion is capped at the **top-K neighbours by edge weight** (`K = 40`) to bound the blowup while keeping the strongest associations. Neighbours are sorted by `(-weight, word)` before truncation — never by raw dict order, which is insertion-dependent and would silently break reproducibility.

**Hard constraints on any emitted path:**

- [ ] **No direct `S–E` edge** — the whole puzzle would be pointless *(explicit spec requirement)*.
- [ ] **No repeated nodes.**
- [ ] **Chordless:** no edge exists between any two non-adjacent members of `{S, w1, w2, w3, w4, E}`.

The chordless rule is worth dwelling on, because it does two jobs at once:

1. **Quality.** With no shortcuts, every rung is load-bearing. Remove any word and the chain breaks — which is exactly what makes the solution feel inevitable in hindsight rather than arbitrary.
2. **Uniqueness, provably.** If no chords exist among the six path members, then **no reordering of the four solution words can form a valid chain.** That eliminates the entire class of "same words, different order" alternates by construction, before distractors are even considered. It reduces the uniqueness problem in §7.6 to "distractors must not create an alternate", which is a far smaller thing to defend.

**Quality gate:** the path's **minimum** edge weight must be `>= 2.0`. One weak link is what makes a chain feel unfair, so we gate on the weakest edge, not the average.

> ⚠️ These constraints are strict, and stacked they may reject the overwhelming majority of candidate paths. **§7.9 analyses exactly how much yield this costs, how to measure it before committing to the design, and a six-tier remedy ladder** — including the case for replacing this BFS with constructive path growth. Read it before implementing this section.

### 7.5 The Brute-Force Solver

The spec's central requirement: prove exactly one valid sequence exists.

```python
from itertools import permutations

def solve_all(g, start, end, bank, length=4):
    """Every ordered arrangement of bank words forming a valid chain start->end."""
    return [
        p for p in permutations(sorted(bank), length)
        if g.has_edge(start, p[0])
        and all(g.has_edge(p[i], p[i + 1]) for i in range(length - 1))
        and g.has_edge(p[-1], end)
    ]

def is_uniquely_solvable(g, start, end, bank):
    return len(solve_all(g, start, end, bank)) == 1
```

**On cost:** `P(11, 4) = 7,920` arrangements × 5 hash lookups ≈ 40k operations per check — roughly a millisecond. There is no reason to hand-roll a pruned DFS here; `itertools.permutations` is correct, obvious at 3am, and fast enough by three orders of magnitude. `sorted(bank)` makes the enumeration order deterministic so failure output is reproducible.

### 7.6 Distractor Selection — Uniqueness by Construction

The naive approach (pick 7 distractors, then test uniqueness, discard the puzzle if it fails) wastes most candidates, because in a graph this dense a random distractor frequently completes some alternate chain.

**Instead, build the bank incrementally and never admit a distractor that breaks uniqueness:**

```python
bank = set(path.solution)
for word in ranked_distractor_pool:                  # deterministic order
    if is_uniquely_solvable(graph, start, end, bank | {word}):
        bank.add(word)
    if len(bank) == BANK_SIZE:
        break
return bank if len(bank) == BANK_SIZE else None      # not enough safe distractors; drop candidate
```

Uniqueness is now an **invariant of the construction**, not a property we hope holds and test for afterwards. The final golden test (§11) verifies it independently on the shipped output — belt and braces, since this is the one property the entire game rests on.

**The distractor pool, in ranked order** — a distractor's job is to be *tempting*, not merely wrong:

| Strategy | What it produces | Why it tempts |
|---|---|---|
| `NearMissStrategy` | 1 hop from a solution word, but a dead end | Feels adjacent to the answer — because it is |
| `SiblingStrategy` | Shares an `IsA` parent with a solution word | Right category, wrong member |
| `SemanticFieldStrategy` | Close to `Start` or `End`, disconnected from the interior | Looks like an obvious opening or closing move |

Ranked by **temptingness** = edge weight to the nearest solution word × frequency-band match. A distractor nobody would ever pick adds difficulty of zero while occupying a tile.

**Two bank-level rejections beyond uniqueness**, both of which look like sloppiness to a player:

- [ ] **No two bank words share a stem.** `moon` and `moons`, `sail` and `sailing`. The `FormOf`/`DerivedFrom` blocklist keeps these out of the *graph edges*, but nothing stops both landing in the same *bank*. Check with a cheap Porter stem comparison across the whole bank.
- [ ] **No bank word is a substring of another** where the shorter is ≥ 4 characters (`art` / `heart` is fine; `star` / `stars` is not — already caught by the stem rule, but this catches compounds the stemmer misses).

> ⚠️ **Both checks must include the endpoints, not just the bank.** Found by
> reading real output: `IRELAND → … → BRANCHES` shipped `branch` as a decoy,
> and `… → WALLS` shipped `wall`. The start and end words sit on screen for
> the whole game, so a decoy echoing one of them is *more* visible than two
> decoys echoing each other — and comparing candidates against the bank alone
> misses exactly that case.

### 7.7 Human Curation — Generate Surplus, Then Review *(decided)*

**ConceptNet is noisy, and algorithmically valid is not the same as fun.** The chain `cat → animal → thing → object → box` passes every automated check in this document and is still a bad puzzle. The heuristics in §7.3–§7.6 raise the hit rate substantially; they do not reach 100%, and nothing that operates purely on graph structure will.

So the pipeline has a human gate:

```
linkage build-graph                       # Phase 1, run once (~20 min)
linkage diagnose --samples 200            # Phase 2, FIRST — yield funnel (§7.9.3)
linkage generate --until-approved 365     # emits candidates.json ranked by quality
linkage review                            # human accept/reject -> approved.json
linkage export                            # append ~a month; repeat as you review
                                          # -> web/public/puzzles/*.json + manifest.json
                                          #    + verification-subgraph.json (§7.10)
```

The `review` TUI:

```
  Candidate 37/800          quality 0.81

  APPLE -> newton -> gravity -> moon -> tide -> OCEAN
           2.4       3.1        2.8     2.2      2.9      (edge weights)

  bank: orbit  pie  physics  wave  salt  cider  comet

  [a]ccept   [r]eject   [s]kip   [e]dit bank   [q]uit
```

Reviewing ~800 candidates at a few seconds each is roughly two evenings of work, and it is the difference between a game people share and one they quit on day three. Accept/reject decisions are keyed by a content hash, so re-running `generate` never loses prior judgements.

> **`--count 800` is a starting guess, not a plan.** If the acceptance rate turns out to be 20%, 800 candidates yields 160 approved — well short of 365. `generate` therefore accepts `--until-approved 365` and tops up from a new seed offset, skipping any candidate whose content hash already has a decision. Never assume one pass is enough; the real number is unknown until the first review session is done.

### 7.7.1 Corpus-Level Quality Control

Every check so far validates a puzzle **in isolation**. A set of 365 individually-good puzzles can still be a bad *year*, and nothing above would catch it. These run at `export` time, across the whole approved set:

- [ ] **Word repetition cap, on a rolling window.** No word appears more than `MAX_WORD_REUSE = 5` times within any `WORD_REUSE_WINDOW = 120` consecutive puzzles (~4 months), counting the bank *and both endpoints*. A word blocked today becomes available again once it falls out the back of the window. Without any cap, high-degree survivors like `gravity` or `river` show up in forty puzzles and the game feels small.
- [ ] **No duplicate `(start, end)` pairs**, in either direction. `APPLE → OCEAN` and `OCEAN → APPLE` are the same puzzle wearing a hat.
- [ ] **No repeated solution chain**, even with different endpoints.
- [ ] **Launch week is hand-picked easy.** Puzzles #1–#7 are chosen manually from the top of the quality ranking, not drawn from the shuffle. First impressions decide whether anyone comes back on day two, and a brutal #1 costs more than a boring one.
- [ ] **Ordering:** the remaining approved puzzles are shuffled with a fixed seed, then assigned sequential dates — so difficulty does not trend across the year.

`export` **fails loudly** if any of these are violated rather than quietly shipping. All are cheap set operations over ~365 × 11 words.

#### Enforcing them, not just checking them

Failing loudly is correct and, on its own, useless. A reviewer judging candidates one at a time cannot track word usage across 365 puzzles, so "the archive is bad, fix it" is not an instruction anyone can act on.

Measured on the first real run: **the top 120 candidates by quality contained 84 words over a cap of 3** (`writing ×11`, `cake ×10`, `desk ×10`). The generator samples endpoint pairs independently, so popular mid-degree words recur constantly across the pool.

So `export` **selects by construction**, exactly as the bank builder does for uniqueness (§7.6): walk the approved candidates best-first and take each one only if it still fits under the cap. `check` then remains as independent verification of the finished archive.

> Word usage counts the **bank plus both endpoints**. The start and end words sit on screen for the entire game, so they are the most visible words in the puzzle — excluding them from the cap would miss the most repetitive thing a player sees.

#### The cost of variety — measured

From a fixed pool of 900 real candidates:

| Rule | Puzzles from 900 | Survival |
|---|---:|---:|
| cap 3, lifetime *(original)* | 134 | 14.9% |
| cap 5, lifetime | 217 | 24.1% |
| **cap 5, 120-puzzle window** *(shipped)* | **365** | **40.6%** |

**The word cap is the only binding constraint** — duplicate pairs and repeated chains accounted for zero rejections at every setting.

**Why the window, not just a bigger number.** A lifetime cap retires a word *forever*, which is stricter than memory actually is: nobody recalls a tile from five months ago. Windowing keeps the game varied where variety is perceptible — across a season — without permanently spending the vocabulary. It reaches a full 365 from the same 900 candidates that a lifetime cap of 5 could only stretch to 217.

Duplicate endpoint pairs and repeated solution chains stay barred **permanently**, not by window. Word reuse is texture and fades; shipping the literal same puzzle twice is a defect at any distance.

Monthly batches under the shipped rule, from that same pool:

```
  month  1: +30   archive= 30    skipped for word cap:   0
  month  3: +30   archive= 90                           35
  month  5: +30   archive=150                          106
  month  6: +30   archive=180                           40   <-- window slides
  month 12: +30   archive=360                          101
```

The dip at month 6 is the window doing its job: puzzles from month 1 have fallen out, so their words are available again.

#### The archive grows a month at a time *(decided)*

The numbers above assume you must review a whole year before launching. **You do not, and pretending otherwise turns curation into a wall nobody climbs.**

`export` appends a **batch** (`BATCH_SIZE = 30`, about a month) to whatever already exists. Existing puzzles keep their ids and dates — numbers people have already shared never move — and the new batch picks up the day after the last one.

```
linkage export              # first run  -> puzzles #1-30,  Oct 1 - Oct 30
linkage export              # next month -> puzzles #31-60, Oct 31 - Nov 29
linkage export --count 60   # a bigger batch when you have the appetite
linkage export --replace    # rebuild from scratch (rarely wanted)
```

**Diversity spans the archive, not the batch.** `select_diverse` is seeded with the words, endpoint pairs and chains already shipped, so month two cannot quietly reuse month one's vocabulary. That is the property that makes incremental building safe rather than a slow-motion way to end up with a repetitive year.

Measured over three real batches:

| Batch | Added | Archive | Skipped for word cap |
|---|---:|---:|---:|
| Month 1 | 30 | 30 | 8 |
| Month 2 | 30 | 60 | 50 |
| Month 3 | 30 | 90 | 161 |

**Launching needs roughly 30-40 approved candidates.** The skip rate climbs as the archive fills, then eases once the window starts sliding — by which point the game is live and curation is a monthly habit rather than a prerequisite.

> Approved candidates are never consumed destructively: any that a batch skips stay in the pool for the next one. Reviewing is cumulative, so a light session still moves the archive forward.

If even the monthly cadence feels heavy, the levers are `MAX_WORD_REUSE` (raise it) or `WORD_REUSE_WINDOW` (shorten it). Both trade perceived variety for review effort, and both are single constants.

### 7.7.2 Quality Scoring — What 900 Real Candidates Taught Us

`QualityScorer` orders the review queue. It is not a taste oracle and does not
try to be; a person still makes every call. But the ordering decides which
puzzles a reviewer sees while they are still fresh, so getting it backwards is
expensive.

The first 900 real candidates showed it *was* backwards:

```
  0.91   SHARK -> ocean -> sailing -> fun -> dancing -> FATIGUE      (mush)
  0.57   PROPOSITION -> statement -> answer -> reply -> echo -> REFLECTION
                                                                    (elegant)
```

**The cause is the Phase 1 hub lesson wearing a different hat.** ConceptNet's
edge weight measures how **obvious** a link is, not how **good** it is. Vague,
highly-connected words earn strong edges precisely by co-occurring with
everything — so a scorer weighted mostly on edge strength selects for banality
and calls it confidence.

> **A word connected to everything connects two ideas only in the way that any
> two ideas are connected.** `ocean -> sailing -> fun -> dancing` has a strong
> edge at every hop and says nothing.

The fix is a **specificity** component: penalise chains whose steps are
high-degree. Degree was the wrong signal for *deleting* a word in Phase 1
(`bird` is rich *and* popular, Risk #19) but it is a fair signal for suspecting
a whole chain of vagueness when every rung is a hub.

| Component | Weight | What it rewards |
|---|---:|---|
| `specificity` | 0.30 | Steps that are concepts, not categories |
| `weakest_link` | 0.20 | No unfair rung — gates on the minimum, never the mean |
| `endpoint_distance` | 0.20 | `apple -> ocean` is a puzzle; `apple -> fruit` is a definition |
| `relation_variety` | 0.15 | Mixed IsA/AtLocation/Causes reads as reasoning, not co-occurrence |
| `overall_strength` | 0.10 | Geometric mean, so one strong edge cannot mask four weak ones |
| `step_balance` | 0.05 | Steady chains feel like a path, not one hop plus four guesses |

Weights sum to 1.0 so `quality` reads as a fraction. The per-component
breakdown is stored with every candidate — when the queue fills with bad
puzzles, it is the only way to tell *which* component is mis-weighted.

### 7.7.3 Review Round 1 — What the Reviewer's Verdicts Showed

25 candidates, judged by hand. **9 approved, 16 rejected — a 36% hit rate.** Raw verdicts live in `engine/reviews/round-01.json`.

**The quality score has almost no predictive power.**

| Signal | Approved | Rejected |
|---|---:|---:|
| **`quality` score** | **0.76** | **0.75** |
| Mean edge weight | 4.00 | 3.28 |
| Weakest link in the chain | 2.62 | 2.36 |
| Spread between mean and weakest | 1.38 | 0.91 |

The scorer this document spends a whole section tuning separates the reviewer's *yes* from their *no* by **one hundredth of a point**. Raw edge strength does discriminate; the composite built on top of it does not.

Two components look actively wrong:

- **`step_balance` is backwards.** It rewards even chains, but approved puzzles had *more* spread between their strongest and weakest link (1.38 vs 0.91). A chain with strong anchors and one real leap is the shape people liked — which is, on reflection, what an "aha" is.
- **`specificity` and `endpoint_distance` cost weight** that the evidence says belongs to plain edge strength.

**Do not retune from these numbers.** 25 verdicts is a small sample from one reviewer, and the honest conclusion is that the scorer should be rebuilt from accumulated verdicts once there are a few hundred — not re-guessed. Its job is ordering a queue, and a queue ordered barely better than chance is still a queue.

#### The banks were uniformly too hard

The reviewer's report: *"all the puzzles have extremely difficult word bank options, the options are too close and potentially can be a replacement."*

Measured: **95% of every bank was a decoy wired to one side of a solution slot** — and identically so in approved and rejected puzzles (6.56 vs 6.75 of 7). It never surfaced as a quality signal because it was not a difference between puzzles; it was *every* puzzle.

The cause was `DistractorSelector` taking the **top-ranked** decoys by temptingness. Every bank was maximally confusing by construction.

> Uniqueness guarantees no decoy actually fits (§7.6) — the golden test proves zero fully-substitutable decoys across all 25. **But a player cannot see that.** A tile attached to one side of a slot looks like it belongs there, and costs a life to disprove. Provable uniqueness and *perceived* uniqueness are different properties, and only the first one was being engineered.

**Fix:** `DISTRACTOR_MIX` draws across hard / medium / easy bands instead of skimming the top. A bank needs texture — a few tiles dismissible on sight are what make the genuinely hard ones feel fair rather than arbitrary.

#### Open items from this round

- [ ] **Approval must not imply scheduling.** A verdict records taste; scheduling is a separate, later decision. Round 1 verdicts are deliberately stored as data and feed nothing. `export` currently reads `decisions.json` and treats *accept* as ready-to-ship — that coupling needs breaking.
- [ ] **Structured rejection reasons.** The reviewer's most useful observation was that a single bad link ruined otherwise-good chains. Letting a reviewer say *which* link failed, and feeding that back into generation, is worth far more than any heuristic guessed from here. To be designed.
- [ ] **Rebuild `QualityScorer` from verdicts** once several hundred exist.

### 7.8 Determinism Checklist

Same inputs must always produce byte-identical output. This is what makes the archive rebuildable years from now.

- [ ] Single `random.Random(SEED)` instance threaded through; never the module-level `random`.
- [ ] Every neighbour iteration sorted by `(-weight, word)` before use.
- [ ] `sorted(bank)` inside the solver.
- [ ] `sorted(G.nodes)` wherever nodes are enumerated.
- [ ] ConceptNet dump pinned by URL **and** verified by SHA-256.
- [ ] `wordfreq` and `networkx` pinned to exact versions in `pyproject.toml`.
- [ ] Provenance recorded as graph attributes; `generate` refuses to run against a graph whose metadata does not match the current config.
- [ ] JSON written with sorted keys and a fixed separator.

---

### 7.9 The Yield Problem (Risk #2) — In Detail

The single technical risk that could sink this project. It deserves more than a row in a table.

#### 7.9.1 What the risk actually is

A path must clear **five** filters simultaneously:

| # | Filter | Demands |
|---|---|---|
| 1 | Exactly 5 edges, `S → w1 → w2 → w3 → w4 → E` | — |
| 2 | No direct `S–E` edge | 1 pair must be a non-edge |
| 3 | **Chordless** | All **10** non-adjacent pairs among the 6 nodes must be non-edges |
| 4 | `min(edge weight) >= 2.0` | All **5** edges must be strong |
| 5 | 7 distractors, each preserving uniqueness | A rich, safe neighbourhood |

**The problem is that these filters fight each other, and they fight the shape of the underlying data.**

**Chords vs. clustering.** ConceptNet was expected to have a **high clustering coefficient** — the technical name for "friends of friends are usually also friends." If `A–B` and `B–C` exist, `A–C` very often exists too. Filter #3 demands the opposite: a locally *tree-like* neighbourhood with no shortcuts. The fear was that we would be searching for tree-like structure inside a graph selected for being clumpy, and that most 5-edge paths would carry a chord.

> ⚠️ **Measured in Phase 1: this prediction was wrong.** The built graph's average clustering coefficient is **0.084**, and the chordless filter keeps **73%** of paths rather than killing 90%+. The relation whitelist and hub removal together produce a graph that is already locally tree-like. See §7.9.6 for the full measurement. The paragraph above is kept because the reasoning was sound and the conclusion was not — that is worth remembering the next time a structural claim goes into this document unmeasured.

**The weight squeeze compounds multiplicatively.** The bulk of `RelatedTo` edges come from ConceptNet's `assoc` dataset at weight 1.0; an edge only reaches 2.0 when several independent sources corroborate it. If a fraction `p` of edges clear the gate, a path needs **all five** to clear it — roughly `p⁵`. At `p = 0.2` that is 0.03% of paths. At `p = 0.3`, 0.24%. A gate that sounds mild applied to one edge is savage applied to five.

**Hub removal cuts connectivity, not just noise.** §7.3 drops the top 1% of nodes by degree. In a scale-free graph those nodes can carry 20–30% of all edges. Removing them is correct for quality and expensive for connectivity: paths get longer and components can fragment.

**The best distractors are the most likely to be rejected.** Near-miss distractors are, by definition, adjacent to solution words — which makes them the *most* likely to complete an alternate chain and get refused by the uniqueness check. The tempting ones are exactly the ones we lose, leaving a bank padded with words nobody would ever pick.

#### 7.9.2 Why low yield is worse than it sounds

The obvious failure — "the generator returns nothing" — is the *good* outcome, because you notice it immediately.

The dangerous one is a **biased sample**. If only 0.01% of paths survive, the survivors are not a random draw. They are systematically the paths living in the sparse, weakly-clustered, tree-like corners of the graph — which in practice means obscure vocabulary and unusual associations. You would get 365 puzzles that pass every automated check, plus a human reviewer who slowly notices that *all of them feel slightly wrong in the same way*.

> **The failure mode to fear is not "no puzzles." It is "365 puzzles that are all subtly wrong in the same direction."** That is far harder to detect and far more expensive to discover late.

#### 7.9.3 Remedy Zero: measure before tuning

Every remedy below is a guess until we have numbers. So the **first thing built in Phase 2 is a diagnostic, not a generator** — roughly 60 lines, run once, and it converts this entire risk from "unknown, possibly fatal" into a table you read off a screen.

```
linkage diagnose --samples 200
```

Reports:

- **Graph shape:** nodes, edges, mean/median degree, and the **average clustering coefficient** — the single number that predicts the chordless kill rate before we write a line of pathfinding.
- **Weight distribution:** fraction of edges at `>= 1.5 / 2.0 / 2.5 / 3.0`, which tells us `p` and therefore `p⁵` directly.
- **A survival funnel** over sampled seeds:

```
  seeds sampled                    200
  5-edge paths found            18,431
  survive: no S-E edge          17,902   (97.1%)
  survive: chordless             1,244   ( 6.9%)   <-- the killer
  survive: min weight >= 2.0        87   ( 7.0%)
  survive: 7 safe distractors       31   (35.6%)
  ------------------------------------------------
  usable candidates per 1k seeds   155
```

You then tune **the stage that is actually killing you**, not the one you guessed. In the illustrative funnel above the chord filter costs 93% and the weight gate a further 93% — so Tiers 1 and 2 below are where the yield is, and widening the vocabulary would be wasted effort.

> **Go / no-go for Phase 2:** if `diagnose` reports **fewer than ~3 usable candidates per 1,000 seeds**, climb the ladder below *before* writing more generator code. Do not build the full pipeline and discover the yield problem at `generate --until-approved 365`.

#### 7.9.4 The remedy ladder

Ordered cheapest-first. Take the first tier that gets yield above target and stop.

**Tier 1 — Turn the weight gate from a hard filter into a soft rank.** *(largest win for the least cost)*

The governing principle, which is worth stating on its own because it applies well beyond this one knob:

> **Hard-filter what a human cannot verify. Soft-rank what a human can see instantly.**

- *Uniqueness* must stay a hard filter — no reviewer can brute-force 7,920 permutations in their head.
- *Chord detection* must stay hard — nobody eyeballs that `S` also connects to `w3`.
- *Edge weakness* should be **soft**. A human takes half a second to see that `moon → sponge` is nonsense. We already have a reviewer reading every shipped puzzle (§7.7) — making the machine reject those paths pre-emptively is spending yield to duplicate work a person does for free.

Change `min(w) >= 2.0` to `min(w) >= 1.5 AND geometric_mean(w) >= 2.0`, and feed edge weight into `QualityScorer` so weak chains sink in the review queue rather than vanishing. Recovers a large multiple of yield at close to zero quality cost.

**Tier 2 — Replace full chordless with the minimal set that preserves the proof.**

Full chordless bans all 10 non-adjacent pairs. The uniqueness-under-reordering guarantee from §7.4 does not need all 10.

> **Proof.** Suppose `S` connects to no path member except `w1`, and `E` connects to none except `w4`. Then any valid chain built from the four solution words must be `S → w1 → ? → ? → w4 → E`, so the two middle slots hold `{w2, w3}` in some order. Order `(w2, w3)` is the intended solution. The only alternative, `(w3, w2)`, requires edges `w1–w3`, `w3–w2` (which exists), and `w2–w4`. It therefore needs **both** `w1–w3` **and** `w2–w4`. Forbidding *either one* is sufficient. ∎

Minimal ban set:

```
  S  ↛  w2, w3, w4, E        (4 pairs)
  E  ↛  w1, w2, w3           (3 pairs)
  NOT (w1–w3  AND  w2–w4)    (1 conditional — only one need be absent)
```

Seven hard bans plus one conditional, against ten. And the two pairs we just relaxed — `w1–w3` and `w2–w4` — are precisely the **2-hop** pairs, the ones most likely to be chords in a highly clustered graph. That is where most of the lost yield lives.

**Identical guarantee, meaningfully looser constraint.** Build full chordless first because the loop is simpler; drop to this if `diagnose` says you need it.

**Tier 3 — Curated hub list instead of a degree percentile.** ✅ **APPLIED in Phase 1** (§7.3, Risk #19)

Percentile removal is blunt. It punishes a word for being *well-connected*, but the actual problem is a word being *generic*. `music`, `fire`, `gold`, and `water` are all high-degree **and** excellent puzzle words. The poison is `thing`, `object`, `stuff`, `item`, `part`, `way`, `kind`, `make`, `use`.

Use the percentile to *generate a candidate list*, then hand-curate ~150 genuinely generic words. Thirty minutes of work; recovers a lot of good vocabulary while removing the actual offenders more precisely than any threshold can.

**Tier 4 — Widen the inputs.**

- Raise `VOCAB_FETCH_N` and `VOCAB_TARGET` together (12,000 → 18,000 and 8,000 → 12,000), keeping roughly the same filter ratio. More nodes, more paths. Cost is obscurity, and the review gate already catches that.
- `BANK_SIZE` 11 → 10 when only 6 safe distractors can be found. The spec allows 10–12, so this is free.

**Tier 5 — Structural: swap `PathFinder` for constructive growth.**

The real fix if yield is still short, and it rests on a realisation worth stating plainly:

> **Bidirectional BFS is solving a harder problem than we actually have.**

BFS is the correct algorithm when you are *given* `S` and `E` and must connect them. We are not given them — **we are generating both**. Nothing in the design requires specific endpoints; it requires a good chain. Search-then-filter discards 99.9% of its work because it finds paths first and checks constraints afterwards.

Constructive growth inverts that: rather than searching for paths that satisfy the constraints, **build paths that cannot violate them.**

```python
# Extend one node at a time; every step pre-checks the constraints.
# A completed walk is valid by construction — nothing to reject afterwards.
def grow(g, rng, length=6):
    path = [rng.choice(mid_frequency_words)]
    while len(path) < length:
        options = [
            n for n in gated_neighbours(g, path[-1])      # weight gate
            if n not in path and creates_no_chord(g, path, n)
        ]
        if not options:
            path.pop()                                     # backtrack
            continue
        path.append(weighted_choice(rng, options))
    return path
```

Yield per attempt approaches 100% with backtracking, against a search that throws almost everything away.

*Bias caveat:* random walks on a weighted graph drift toward high-degree nodes, which would quietly reintroduce the hub problem. Sample neighbours with probability inversely proportional to degree, or uniformly from the gated set.

Architecturally this is **one new class behind the existing interface**:

```python
class PathFinder(Protocol):
    def find(self, budget: int) -> Iterator[Path]: ...

class BidirectionalBFSFinder: ...    # primary, per spec — gives more diverse S/E pairs
class ConstructiveGrowthFinder: ...  # fallback — same interface, same output type
```

`DistractorSelector`, `UniquenessValidator`, `QualityScorer`, and every exporter are untouched. **This is the concrete payoff of the Open/Closed boundary in §5:** the riskiest component in the system is the one we can replace without touching anything around it. The architecture was chosen partly for this.

**Tier 6 — Add a second data source.** *(last resort)*

Union WordNet hypernym/meronym chains, or the Wikipedia link graph, into the same `networkx.Graph`. Genuinely more code and a new parsing/normalisation problem. Only if Tiers 1–5 combined still fall short.

#### 7.9.5 Measured Results (Phase 1, 2026-09-05)

Built from ConceptNet 5.7 with the filters in §7.1–§7.3. **34,074,917 lines parsed in 3m18s, 0 malformed.**

Measured twice: once with P99 degree pruning on, and again after it was removed (Risk #19). **SHIPPED is the right-hand column.**

```
                              P99 pruning ON      SHIPPED (curated only)
  nodes                              7,524                       7,625
  edges                             46,795                      54,373
  largest component          7,518 (99.9%)               7,619 (99.9%)
  mean / median degree         12.44 /  8                  14.26 /  9
  max degree                            77                 208 (animal)
  avg clustering                    0.0839                      0.0912
  transitivity                      0.0416                      0.0437

  edge weights  >= 1.5               19.8%                       20.6%
                >= 2.0               18.7%                       19.4%
                >= 2.5                5.0%                        5.6%
                >= 3.0                3.4%                        3.9%

  survival funnel        (25 seeds)          (10 seeds, same top-25 cap)
    5-edge paths                  32,982,070                  17,113,447
    no S-E edge          32,645,394 (99.0%)         16,962,778 (99.1%)
    chordless            23,895,424 (73.2%)         11,554,863 (68.1%)
    min weight >= 2.0        62,039  (0.3%)             45,734  (0.4%)

  usable per 1,000 seeds         2,481,560                   4,573,400
```

**Removing the pruner nearly doubled usable yield**, from 2.48M to 4.57M per 1,000 seeds. Both figures dwarf the §7.9.3 go/no-go threshold of 3.

Clustering rose from 0.0839 to 0.0912 and chordless survival fell from 73.2% to 68.1% — exactly as predicted, since the restored words are precisely the well-connected ones. The effect is real, small, and paid for many times over by the extra density. **Chordless still costs ~32%, nowhere near the ~93% the plan originally assumed.**

**Four conclusions, all of which change the plan:**

1. **Risk #2 is closed.** The §7.9.3 go/no-go threshold was 3 usable candidates per 1,000 seeds. Measured: **~2.5 million**. Yield is not the constraint and never was.
2. **Chordless is cheap — keep it at `full`.** It costs 27%, not 93%. **§7.9.4 Tier 2 is unnecessary**; do not weaken the constraint or the uniqueness proof to buy yield we do not need.
3. **The weight gate is the whole squeeze, exactly as the `p⁵` arithmetic predicted** (p = 0.187 → 0.023%; observed 0.3%, the gap being that path edges are not independent). **Tier 1 remains the right first lever** *if* one is ever needed — but with 62,039 survivors from 25 seeds, it is not needed. Leave `MIN_EDGE_WEIGHT = 2.0`. Note the cliff between 2.0 (18.7%) and 2.5 (5.0%): 2.0 sits on a natural boundary.
4. **Tier 3 is now urgent, and for the reason it predicted.** P99 removed 75 words at `degree > 82`. They were: `animal, art, attack, ball, bar, base, bed, bill, bird, box, break, bridge, ...` — **these are good puzzle words, not generic noise.** The curated `GENERIC_HUBS` list already removes the actual poison (`thing`, `object`, `stuff`) at the vocabulary stage, so the degree percentile is now redundant *and* doing net harm. See Risk #19.

**The risk has moved, not disappeared.** With ~2.5M candidate paths for 365 slots, the binding constraint is no longer *finding* paths but *choosing* them. `QualityScorer` and the human review gate are now the entire game — Risk #1, not Risk #2, is what this project lives or dies on.

**One implementation consequence:** 25 seeds produced 33 million paths. The generator must **never enumerate exhaustively** — it needs early termination and per-seed budgets, or `generate` will run for hours producing candidates nobody will ever review.

#### 7.9.6 Summary

**Measured and closed (§7.9.5).** Yield came in at ~2.5 million usable paths per 1,000 seeds against a go/no-go threshold of 3. The clustering half of the thesis was wrong — chordless costs 27%, not 93% — while the `p⁵` weight arithmetic was exactly right, and is the only real squeeze. None of the six remedy tiers needs to be applied for yield.

What survives from this analysis:

- **Tier 3 is now a live action item** (Risk #19): degree-percentile pruning is removing good puzzle words and is redundant with the curated `GENERIC_HUBS` list.
- **Tiers 1, 2, 4, 5, 6 stay documented but unused.** They are the ladder to climb if the constraint set ever tightens — for a longer chain, a stricter weight gate, or a smaller vocabulary.
- **The `p⁵` arithmetic is the transferable lesson.** Any filter applied to all five path edges is savage even when it looks mild on one. Check that before adding a per-edge constraint.

**The risk has moved to Risk #1.** With millions of candidates for 365 slots, finding paths is free and *choosing* them is everything. `QualityScorer` and the review gate now carry the project.

**Concrete action: `linkage diagnose` still ships in Phase 2** — not to answer this question, which is answered, but so the funnel is re-measurable the moment any filter changes.

---

### 7.10 The Verification Subgraph — Making the Golden Test Runnable in CI

**A contradiction that would otherwise be discovered the first time CI runs.**

The most important test in this project (§11, `test_output_invariants.py`) re-solves every shipped puzzle and asserts exactly one solution exists. To do that it needs the **graph**. The graph needs the **1.2 GB ConceptNet dump**, which §12 explicitly forbids CI from touching. As specified, *the one test the entire game rests on could never run on a pull request.*

The fix is small and falls out of the maths. Verifying a puzzle only requires the edges **among that puzzle's own words** — the 11 bank words plus `start` and `end`. That is 13 nodes, so at most `C(13, 2) = 78` pairs per puzzle. Across 365 puzzles that is **under 30,000 edges** — a few hundred KB of JSON.

So `linkage export` emits one extra file — **into `engine/fixtures/`, deliberately not into `web/public/`**, because it is a plaintext answer key and publishing it would undo §3.2:

```jsonc
// engine/fixtures/verification-subgraph.json   (committed, ~300 KB, NOT served)
{
  "schemaVersion": 1,
  "note": "Induced subgraph over every shipped puzzle's bank + endpoints. Verification only.",
  "edges": [["apple", "newton", 2.4], ["newton", "gravity", 3.1], ...]
}
```

The golden test loads this instead of the pickle:

- [ ] Runs in CI on every PR, in seconds, with **no dataset and no `networkx` graph build**.
- [ ] Contains *every* edge among the relevant words, so a false "unique" is impossible — if an alternate chain existed, its edges are present here by construction.
- [ ] Doubles as the fixture for the Playwright e2e test, which needs a real solvable puzzle.

> ⚠️ **The subgraph must be the induced subgraph — every edge among those 13 nodes, not just the 5 solution edges.** Exporting only the solution path would make the uniqueness test vacuous: it would find one solution because it was handed only one solution's worth of edges. This is the single way to get this file wrong, and it fails silently by passing. `test_output_invariants.py` asserts the edge count is consistent with a full induced subgraph before trusting it.

**It lives outside the web root on purpose.** The file is unobfuscated and contains enough to derive every answer, so it must never be served. It is a build artefact read only by `pytest` and the Playwright fixture. It is still committed — CI needs it, and it is small — but `web/public/` never sees it and the deploy never publishes it.
