# Linkage — Project Blueprint

> A daily mini word puzzle about the hidden connective tissue between ideas.
> `APPLE → newton → gravity → moon → tide → OCEAN`

**Status:** Planning complete · No code written yet
**Repo:** `TechGenius-Karan/Linkage`
**Last updated:** 2026-09-05

---

## Table of Contents

1. [Context & Philosophy](#1-context--philosophy)
2. [Game Design & Mechanics](#2-game-design--mechanics)
3. [The Data Contract](#3-the-data-contract)
4. [Architecture](#4-architecture)
5. [SOLID, Applied Concretely](#5-solid-applied-concretely)
6. [Repository Layout](#6-repository-layout)
7. [Deep Dive — Python Generation Engine](#7-deep-dive--python-generation-engine)
8. [Deep Dive — TypeScript Client](#8-deep-dive--typescript-client)
9. [Backend: Recommendation & Rationale](#9-backend-recommendation--rationale)
10. [Implementation Phases](#10-implementation-phases)
11. [Testing Strategy](#11-testing-strategy)
12. [CI/CD & Deployment](#12-cicd--deployment)
13. [Risk Register](#13-risk-register)
14. [Explicitly Out of Scope](#14-explicitly-out-of-scope)
15. [Problem → Solution Index](#15-problem--solution-index)

- [Appendix A — Tunable Constants](#appendix-a--tunable-constants)
- [Appendix B — Decision Log](#appendix-b--decision-log)
- [Appendix C — Command Reference](#appendix-c--command-reference)

**Start here:** §7.9 (the yield problem) and §7.10 (making CI able to verify) are the two sections that most change how the code gets written. §15 indexes every problem in this document against the section that solves it.

---

## 1. Context & Philosophy

### 1.1 The Core Concept

Linkage is a game of **conceptual lateral thinking**. It explores the hidden connective tissue between seemingly unrelated ideas. It is not a spelling game, not an anagram game, and not a vocabulary test.

### 1.2 The Feeling

The game should evoke a series of **"aha!" moments**. It is not about spelling or strict definitions; it is about how the human brain naturally associates concepts (e.g. `Apple → Newton → Gravity`). The challenge lies in navigating the noise of plausible distractors to find the perfect logical thread.

### 1.3 The Design North Star

Every technical decision in this document is subordinate to one test:

> **Does the player, on seeing the solution, feel clever — or feel cheated?**

This is why the generator is not fully automated (§7.7), why hub words are banned (§7.3), why chordless paths are enforced (§7.4), and why we optimise for *tempting* distractors rather than merely *valid* ones (§7.6). An algorithmically perfect puzzle that reads as arbitrary is a failed puzzle.

### 1.4 Non-Negotiable Product Constraints

| Constraint | Consequence |
|---|---|
| **Zero hosting cost** | Static client. No always-on server. Puzzles precomputed offline. |
| **Sub-60-second session** | 4 slots, one board, no tutorial, no accounts. |
| **Mobile-first** | Tap-to-place, thumb-reachable board, no hover-dependent affordances. |
| **Shareable** | Spoiler-free emoji grid. The share text *is* the growth channel. |
| **Deterministic** | Same seed + same dataset ⇒ byte-identical output. Rebuildable forever. |

---

## 2. Game Design & Mechanics

### 2.1 The Goal

Connect a **Start Word** to an **End Word** using a ladder of exactly **4 intermediate words** based on conceptual associations.

### 2.2 The Board

A vertical ladder: Start word fixed at the top, End word fixed at the bottom, four empty slots between them, word bank below.

```
                APPLE          <- Start (fixed)
                  |
             [    ?    ]       <- Slot 1
             [    ?    ]       <- Slot 2
             [    ?    ]       <- Slot 3
             [    ?    ]       <- Slot 4
                  |
                OCEAN          <- End (fixed)

  WORD BANK (shuffled, 11 tiles)
  [ pie ] [ gravity ] [ salt ] [ moon  ]
  [ tide] [ physics ] [newton] [ orbit ]
  [ wave] [  cider  ] [comet ]
```

### 2.3 The Word Bank

- **11 tiles** (spec allows 10–12; 11 is the default constant `BANK_SIZE`).
- **4** are the correct sequence.
- **7** are semantic red herrings — see §7.6 for how they are chosen.
- Bank order is **shuffled at generation time** with a seed derived from the puzzle ID, so tile positions are stable across refreshes and identical for every player.

### 2.4 Interaction Model — Tap-to-Place *(decided)*

**v1 ships tap-to-place only.**

1. Tap a bank tile → it enters `selected` state.
2. Tap a slot → the tile moves into the slot.
3. Tap a filled slot with nothing selected → the tile returns to the bank.
4. Tap a filled slot while a tile is selected → the two **swap**.

**Why not drag-and-drop in v1:** native HTML5 drag-and-drop does not fire on touch devices, so "drag" on mobile means shipping a library or hand-rolling pointer events. Tap-to-place needs zero dependencies, behaves identically on mobile and desktop, and is keyboard-accessible for free.

**Phase 5** layers `@dnd-kit/core` on top as a pure enhancement — its sensors dispatch the **same** `PLACE_TILE` / `REMOVE_TILE` reducer actions. The game logic never learns that drag exists.

### 2.5 Feedback Model — Count-Only *(decided)*

This is the defining mechanic, and the hardest of the three candidate models.

- Player fills **all 4 slots**, then presses **Check**.
- The game reports **only how many slots hold the correct word** — never *which*.
- `correctCount = |{ i : placed[i] === solution[i] }|` — strictly positional.

```
   ♥ ♥ ♥      Attempt 1   2 of 4 correct
   ♥ ♥ ♡      Attempt 2   3 of 4 correct
   ♥ ♡ ♡      Attempt 3   4 of 4  -- Solved!
```

**Design consequences of choosing count-only:**

| Consequence | Handling |
|---|---|
| Feedback is a *nudge*, not a solving mechanism. Players must reason semantically. | This is the point — it protects the "aha". Positional feedback turns Linkage into a deduction grind. |
| Inherently colourblind-safe — the signal is a *number*, stated in text. | Colour is decoration, never the sole channel. Free accessibility win. |
| A player can legitimately score 3/4 (three solution words placed right, a distractor in the fourth slot). | Not a bug. Noted so nobody "fixes" it later. |

### 2.5.1 Three Lives *(decided)*

**`MAX_ATTEMPTS = 3`**, presented to the player as **three lives** (`♥ ♥ ♥`), not as an attempt counter.

The reframe is the point. "3 of 6 attempts used" reads as a budget to spend; **three hearts read as stakes**. It changes how a player approaches the board — from probing to committing.

**What 3 lives does to the game:**

- With `P(11, 4) = 7,920` possible arrangements and ~2.3 bits of feedback per guess, **you cannot deduce your way to the answer in three tries.** That is intentional. Feedback becomes pure warmer/colder confirmation of a reading you already believe, never a solving tool. It pushes all the weight back onto semantic reasoning, which is what Linkage is actually about.
- The share grid is at most **3 rows** — tighter and more legible than 6.
- Hearts, not a number, in the UI: `♥ ♥ ♥` → `♥ ♥ ♡` → `♥ ♡ ♡`. Lost hearts stay visible (greyed), so the cost is felt rather than read.

> ⚠️ **The one thing to watch: win rate.** Wordle's ~95%+ win rate is a large part of why people share it — nobody posts a failure. Three lives plus count-only feedback is a genuinely hard combination, and if the win rate lands below ~50% the share loop dies quietly.
>
> **If that happens, the lever to pull is puzzle difficulty, not more lives** — "3 lives" is now part of the game's identity, and difficulty is the softer knob. In order: reduce distractor temptingness (§7.6), raise `MIN_EDGE_WEIGHT` so chains read more obviously, tighten the review gate. Adding a fourth heart is the last resort, not the first.
>
> Tracked as Risk #11. Measure this in playtest before launch, not after.

**Loss condition:** 3 failed attempts → `lost`. The full solution chain is then revealed.

### 2.6 The Daily Cycle

- One puzzle per day, resetting at **midnight local time**.
- `puzzleNumber = daysBetween(EPOCH_DATE, todayLocal)`.
- Computed with **date-only arithmetic** (`new Date(y, m, d)` for both endpoints), never raw millisecond subtraction — otherwise DST transitions shift the puzzle by one for half the year. See §8.3.
- Timezone-hopping to reach tomorrow's puzzle early is accepted, exactly as Wordle does.

### 2.7 Sharing

Wordle-shaped and spoiler-free. One row per attempt; the number of filled squares equals `correctCount`.

```
Linkage #142  3/3

[Y][Y][ ][ ]        (rendered with emoji: yellow / white / green)
[Y][Y][Y][ ]
[G][G][G][G]

https://techgenius-karan.github.io/Linkage/
```

- 🟨 — one correct placement in that attempt.
- ⬜ — one incorrect placement.
- 🟩 — the winning row.
- A loss renders `X/3` with all three rows.
- At most 3 rows, so the whole grid fits any post without wrapping.

Because squares are **left-packed rather than positional**, the grid leaks *zero* information about which slots were right. A friend seeing your grid learns your struggle, not the answer. This falls out naturally from the count-only feedback model — the two decisions reinforce each other.

Copy via `navigator.clipboard.writeText`, with a hidden `<textarea>` + `document.execCommand('copy')` fallback for older iOS Safari.

### 2.8 Persistence

`localStorage`, versioned keys, single-device.

| Key | Contents |
|---|---|
| `linkage:v1:progress:<id>` | In-flight board state for puzzle `<id>` — survives a mid-game refresh. |
| `linkage:v1:stats` | `gamesPlayed`, `wins`, `currentStreak`, `maxStreak`, `distribution[1..3]`, `lastCompletedId` |

- Streak breaks when `puzzleId !== lastCompletedId + 1`.
- Progress entries older than 7 days are pruned on load.
- Every read is defensive: a corrupt, absent, or unparseable value yields a fresh game — never a crash. Private-browsing mode where `localStorage` throws on write is caught and degrades to in-memory.

---

## 3. The Data Contract

The single interface between the Python engine and the TypeScript client. **Changing this shape is a breaking change and requires a `schemaVersion` bump on both sides.**

### 3.1 Decoded Puzzle

```jsonc
{
  "schemaVersion": 1,
  "id": 142,                                           // stable puzzle number, shown in share text
  "date": "2027-02-19",                                // ISO date this puzzle is scheduled for
  "start": "apple",
  "end": "ocean",
  "solution": ["newton", "gravity", "moon", "tide"],   // ordered, slots 1..4
  "bank": [                                            // pre-shuffled; solution + distractors
    "pie", "gravity", "salt", "moon", "tide",
    "physics", "newton", "orbit", "wave", "cider", "comet"
  ]
}
```

> `date` must equal `EPOCH_DATE + (id - 1)` days. The golden test (§11) asserts this — a drift between `id` and `date` would show the wrong puzzle number in every share.

**`meta` is stripped on export.** The generator carries `minEdgeWeight`, `qualityScore`, and the relation sequence through `candidates.json` and `approved.json` for review and debugging, but they are **removed before writing the per-day files**. They are dead payload weight, and `meta.relations` is a mild hint at the chain's shape.

### 3.1.1 Word Normalisation

One canonical form, decided once, or the two halves will disagree about what a word *is*:

| Rule | Value |
|---|---|
| Case | **Lowercase everywhere** in data. Display casing (`APPLE`) is a CSS/UI concern only — `text-transform: uppercase`, never stored. |
| Character set | **ASCII `[a-z]` only.** No accents, digits, hyphens, or apostrophes. |
| Multiword | **Excluded.** ConceptNet uses `/c/en/ice_cream`; any URI containing `_` is dropped at parse time. Long tiles break the mobile layout and read as phrases, not concepts. |
| Length | 3–12 characters. Longer words overflow a tile at 320 px. |
| Comparison | Plain `===` / `==` on the normalised string. `tileId` **is** the word — the bank is a set of unique words, so no separate identity is needed. |

### 3.2 On-Disk Shape — Per-Day + Obfuscated *(decided)*

The client fetches **only today's file** (~1 KB) instead of a ~400 KB bundle containing all 365 answers.

```
web/public/puzzles/2026-09-05.json   ->   { "v": 1, "d": "k3Nf9a2Lp8..." }
```

**Codec** — deliberately *obfuscation, not encryption*:

```
encode:  utf8_bytes(json)  ->  XOR with repeating key = utf8_bytes(dateISO)  ->  base64
decode:  base64  ->  XOR with same key  ->  utf8  ->  JSON.parse
```

This stops casual DevTools snooping and shrinks the payload ~400×. A determined person can still recover it, and that is fine — Wordle shipped its entire word list in the bundle and survived. **We are not pretending this is security.**

> ⚠️ **The codec must be byte-identical across Python and TypeScript.** This is the single most likely place for a silent cross-language bug: UTF-8 multibyte handling, and `atob` returning a *binary string* rather than bytes. §11 specifies a Python-generated fixture that the TS suite must decode — that test is non-negotiable.

### 3.3 Manifest

```jsonc
// web/public/puzzles/manifest.json
{ "schemaVersion": 1, "epoch": "2026-10-01", "count": 365, "firstId": 1 }
```

Lets the client compute the puzzle number and detect "no puzzle today" (before launch, or after the archive runs dry) without a 404 round-trip.

---

## 4. Architecture

### 4.1 Chosen Architecture: Three-Tier, Applied Twice

**Three-tier (Presentation / Application / Data) is the right fit here**, and not merely because it was requested. The justification:

1. **The game rules are the crown jewels.** Pathfinding, uniqueness validation, and scoring must be testable without a browser, a DOM, or a network. A logic tier with zero framework imports gives us that on day one.
2. **Two independent programs share one contract.** The Python engine and the TS client never call each other — they meet only at `puzzles/*.json`. That is already a tier boundary; naming it makes it enforceable.
3. **The data source is genuinely volatile.** Today: static per-day files. Plausibly tomorrow: a Worker endpoint, an archive mode, a CDN. A data tier behind an interface absorbs that. `fetch` calls sprayed through components would not.

**Applied twice** — the same three tiers appear in both halves of the system, which keeps one mental model for the whole repo:

```
  OFFLINE — Python engine          runs on a laptop, roughly monthly
  ------------------------------------------------------------------
    Presentation    cli.py, review.py
                    Typer commands, human review TUI
         |
    Domain          pathfinder, distractors, validator, scoring
                    Pure functions. No I/O. No network.
         |
    Data Access     conceptnet, vocabulary, graph_store, exporters
                    Downloads, parses, pickles, writes JSON
         |
         v
    ============================================================
      web/public/puzzles/YYYY-MM-DD.json
      THE ONLY INTERFACE BETWEEN THE TWO HALVES
    ============================================================
         |
         v
  ONLINE — TypeScript client       static, in the browser
  ------------------------------------------------------------------
    Presentation    ui/ — Board, Slot, WordBank, Tile, ShareModal
                    Props in, events out. Zero game rules.
         |
    Domain          engine/ — gameReducer, dailyIndex, share, stats
                    No React. No DOM. No fetch.
         |
    Data Access     data/ — PuzzleRepository, ProgressStore, codec
                    fetch, localStorage, decode
```

### 4.2 The Dependency Rule

> **Dependencies point inward. The Domain tier imports nothing from Presentation or Data.**

Concretely, and enforceable by lint rule:

| Tier | May import | Must never import |
|---|---|---|
| `ui/` | `engine/`, `data/`, React, Tailwind | — |
| `engine/` | *only its own types* | `react`, `fetch`, `localStorage`, `window`, `document` |
| `data/` | `engine/` types only | `react`, anything in `ui/` |

The interfaces that `data/` implements (`PuzzleRepository`, `ProgressStore`) are **declared in `engine/`**. This is Dependency Inversion in its load-bearing form: the logic tier owns the contract, the data tier conforms to it. Swapping static files for a Worker endpoint later touches exactly one file.

**Enforcement:** an ESLint `no-restricted-imports` rule scoped to `src/engine/**`. Not a convention we hope to remember — a build failure.

### 4.3 A Note on Pragmatism

This document specifies layering, interfaces, and strategy objects **where they earn their keep** — every interface listed below has at least two real implementations, usually the real one plus a test stub that removes the network or the clock from a test.

What this project deliberately does **not** get: a DI container, an abstract factory, a repository interface with a single implementation, a `BaseService` class, or a config file for a value that never changes. SOLID is a tool for making change cheap; ceremony that enables no substitution is cost with extra steps.

---

## 5. SOLID, Applied Concretely

Not a definitions list — the actual class-by-class application in this codebase.

### S — Single Responsibility

Each generator component has exactly **one reason to change**:

| Class | Sole responsibility | Changes only when... |
|---|---|---|
| `ConceptNetLoader` | Parse the raw dump into filtered edges | ConceptNet's file format changes |
| `GraphBuilder` | Assemble a `networkx.Graph` from edges | Graph shape/weighting policy changes |
| `PathFinder` | Find chordless 5-edge chains | The pathfinding algorithm changes |
| `DistractorSelector` | Choose red herrings for a given path | Distractor policy changes |
| `UniquenessValidator` | Prove exactly one solution exists | The solver changes |
| `QualityScorer` | Rank candidates for human review | Our taste in puzzles changes |
| `PuzzleExporter` | Serialise, obfuscate, write per-day files | The data contract changes |

The anti-pattern being avoided: one `PuzzleGenerator` god-class where tweaking distractor policy risks breaking pathfinding.

### O — Open/Closed

`DistractorStrategy` is the one place we genuinely expect new behaviour without modifying existing code:

```python
class DistractorStrategy(Protocol):
    def propose(self, graph: Graph, path: Path, k: int) -> list[ScoredWord]: ...

# Three real implementations from day one — the abstraction is earned, not speculative:
class NearMissStrategy:      ...  # 1 hop from a solution word, but a dead end
class SiblingStrategy:       ...  # shares an IsA parent with a solution word
class SemanticFieldStrategy: ...  # close to Start or End, disconnected from the interior
```

Adding a fourth (say, phonetic near-misses) is a new file plus one registry entry. `DistractorSelector` is never edited.

### L — Liskov Substitution

Every `PuzzleRepository` is substitutable, and the test suite proves it by running the identical behavioural contract against all implementations:

```ts
// engine/ports.ts  — the interface lives in the DOMAIN tier
export interface PuzzleRepository {
  load(puzzleId: number, date: string): Promise<Puzzle>;   // rejects with PuzzleNotFound
}
```

- `HttpPuzzleRepository` — real: fetch + decode.
- `StubPuzzleRepository` — tests: in-memory fixture, no network, no clock.

Both must reject with the **same** `PuzzleNotFound` error type. A stub that resolved `null` instead would violate LSP and break every consumer that relies on the contract.

### I — Interface Segregation

The client gets **two narrow ports**, not one fat `GameService`:

```ts
export interface PuzzleRepository { load(id: number, date: string): Promise<Puzzle>; }
export interface ProgressStore {
  readProgress(id: number): GameState | null;
  writeProgress(id: number, s: GameState): void;
  readStats(): Stats;
  writeStats(s: Stats): void;
}
```

The share modal needs neither. It takes a plain `GameState` and returns a string. Nothing depends on methods it does not call.

### D — Dependency Inversion

The load-bearing rule of this codebase:

- `engine/ports.ts` **declares** `PuzzleRepository` and `ProgressStore`.
- `data/httpPuzzleRepository.ts` and `data/localStorageProgressStore.ts` **implement** them.
- `main.tsx` is the **only** file that names concrete implementations — the composition root, wired once:

```tsx
// main.tsx — the single place where abstract meets concrete
const repo  = new HttpPuzzleRepository(import.meta.env.BASE_URL);
const store = new LocalStorageProgressStore();
render(<App repo={repo} store={store} />);
```

Every test builds `<App>` with stubs. No mocking framework, no module interception, no `jest.mock`. That property alone justifies the two interfaces.

---

## 6. Repository Layout

Two top-level programs, no monorepo tooling — they share zero dependencies, so npm workspaces or Nx would be pure overhead.

```
Linkage/
├── planning.md                       <- this document
├── README.md
├── .gitignore                        <- data/raw/, data/*.gpickle, node_modules, dist
│
├── engine/                           # ===== PYTHON: offline generation =====
│   ├── pyproject.toml                # deps: networkx, wordfreq, typer, orjson, tqdm
│   ├── src/linkage_engine/
│   │   ├── __main__.py
│   │   ├── cli.py                    # TIER 1  build-graph | generate | review | export
│   │   ├── review.py                 # TIER 1  human curation TUI
│   │   ├── config.py                 # all tunable constants in ONE place
│   │   ├── domain/                   # TIER 2  pure. no I/O, no network, no filesystem.
│   │   │   ├── models.py             #   frozen dataclasses: Path, Candidate, Puzzle
│   │   │   ├── pathfinder.py         #   bidirectional bounded BFS
│   │   │   ├── distractors.py        #   DistractorStrategy protocol + 3 impls
│   │   │   ├── validator.py          #   brute-force solver + uniqueness proof
│   │   │   └── scoring.py            #   QualityScorer
│   │   └── data/                     # TIER 3  everything that touches the outside world
│   │       ├── conceptnet.py         #   download + stream-parse the dump
│   │       ├── vocabulary.py         #   wordfreq top-N + stoplist filtering
│   │       ├── graph_store.py        #   pickle save/load (see NetworkX 3.x note, §7.2)
│   │       ├── codec.py              #   XOR + base64 encoder (mirror of the TS decoder)
│   │       └── exporters.py          #   candidates.json / approved.json / per-day files
│   ├── fixtures/                     # committed, NOT served — see §7.10
│   │   ├── verification-subgraph.json  #   induced subgraph; lets CI run the golden test
│   │   └── codec-fixture.json          #   Python-encoded payload the TS suite must decode
│   └── tests/
│       ├── test_validator.py         # uniqueness solver correctness
│       ├── test_pathfinder.py        # chordless, no repeats, correct length
│       ├── test_codec.py             # round-trip + emits the TS fixture
│       └── test_output_invariants.py # THE golden test — re-solves every shipped puzzle
│
├── web/                              # ===== TYPESCRIPT: the client =====
│   ├── package.json                  # deps: react, react-dom  (that is the whole list for v1)
│   ├── vite.config.ts                # base: '/Linkage/'  <- required for GH Pages
│   ├── tailwind.config.ts
│   ├── public/puzzles/               # generated by the engine, committed to git
│   │   ├── manifest.json
│   │   └── 2026-10-01.json ...
│   ├── src/
│   │   ├── main.tsx                  # TIER 1  composition root — the ONLY place with `new`
│   │   ├── App.tsx                   # TIER 1  wiring + loading/error states
│   │   ├── ui/                       # TIER 1  presentational, props in / events out
│   │   │   ├── Board.tsx  Slot.tsx  WordBank.tsx  Tile.tsx
│   │   │   ├── AttemptHistory.tsx  ShareModal.tsx  StatsPanel.tsx
│   │   │   └── HowToPlay.tsx
│   │   ├── engine/                   # TIER 2  ZERO react/DOM imports (lint-enforced)
│   │   │   ├── types.ts              #   Puzzle, GameState, Action, Stats
│   │   │   ├── ports.ts              #   PuzzleRepository, ProgressStore interfaces
│   │   │   ├── gameReducer.ts        #   makeGameReducer(puzzle) -> reducer
│   │   │   ├── dailyIndex.ts         #   DST-safe puzzle-number arithmetic
│   │   │   ├── share.ts              #   emoji grid builder
│   │   │   └── stats.ts              #   streak + distribution updates
│   │   └── data/                     # TIER 3
│   │       ├── httpPuzzleRepository.ts
│   │       ├── localStorageProgressStore.ts
│   │       └── codec.ts              #   XOR + base64 decoder (mirror of the Python encoder)
│   └── tests/
│       ├── gameReducer.test.ts  dailyIndex.test.ts  share.test.ts
│       ├── codec.test.ts             # decodes the Python-generated fixture
│       └── e2e/play.spec.ts          # Playwright: load -> solve -> share
│
├── data/                             # gitignored — large, regenerable
│   ├── raw/conceptnet-assertions-5.7.0.csv.gz
│   └── linkage-graph.gpickle
│
└── .github/workflows/
    ├── test.yml                      # pytest + vitest on every PR
    └── deploy.yml                    # build + deploy to GitHub Pages on main
```

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
linkage export --start-date 2026-10-01    # -> web/public/puzzles/*.json + manifest.json
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

### 7.7.1 Corpus-Level Quality Control

Every check so far validates a puzzle **in isolation**. A set of 365 individually-good puzzles can still be a bad *year*, and nothing above would catch it. These run at `export` time, across the whole approved set:

- [ ] **Word repetition cap.** No word appears in more than `MAX_WORD_REUSE = 3` puzzles across the year, counting bank appearances, not just solutions. Without this, high-degree survivors like `gravity` or `river` show up in forty puzzles and the game feels small.
- [ ] **No duplicate `(start, end)` pairs**, in either direction. `APPLE → OCEAN` and `OCEAN → APPLE` are the same puzzle wearing a hat.
- [ ] **No repeated solution chain**, even with different endpoints.
- [ ] **Launch week is hand-picked easy.** Puzzles #1–#7 are chosen manually from the top of the quality ranking, not drawn from the shuffle. First impressions decide whether anyone comes back on day two, and a brutal #1 costs more than a boring one.
- [ ] **Ordering:** the remaining approved puzzles are shuffled with a fixed seed, then assigned sequential dates — so difficulty does not trend across the year.

`export` **fails loudly** if any of these are violated rather than quietly shipping. All are cheap set operations over ~365 × 11 words.

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

---

## 8. Deep Dive — TypeScript Client

### 8.1 Stack

| Choice | Why |
|---|---|
| **Vite + React + TypeScript** | Per spec. Fast dev loop, trivial static build. |
| **Tailwind** | Per spec. No CSS-in-JS runtime, no stylesheet drift. |
| **`useReducer`, no state library** | Total state is 4 slots + an attempts array. Redux/Zustand would be strictly more code than the thing they manage. |
| **No drag library in v1** | §2.4. `@dnd-kit` arrives in Phase 5 only if drag is still wanted after playtesting tap. |
| **Vitest + Playwright** | Vitest shares Vite's config. One Playwright smoke test, not a suite. |

**Total runtime dependencies for v1: `react` and `react-dom`.** Every other need is met by the platform.

### 8.2 The Reducer — Tier 2, Framework-Free

```ts
type GameStatus = 'playing' | 'won' | 'lost';

interface Attempt {
  tiles: [string, string, string, string];
  correctCount: number;        // 0..4 — the ONLY thing the player learns
}

interface GameState {
  puzzleId:     number;
  slots:        (string | null)[];   // length 4
  attempts:     Attempt[];
  status:       GameStatus;
  selectedTile: string | null;       // tap-to-place selection
}

type Action =
  | { type: 'SELECT_TILE'; tileId: string }
  | { type: 'PLACE_TILE';  slot: number }     // places the currently selected tile
  | { type: 'REMOVE_TILE'; slot: number }
  | { type: 'SUBMIT' }
  | { type: 'RESTORE'; state: GameState };
```

The reducer must compare against the solution, but the solution must not live in `GameState` (it would then be trivially inspectable in React DevTools and would have to be serialised into `localStorage`). So the reducer is **curried over the puzzle**:

```ts
export function makeGameReducer(puzzle: Puzzle): (s: GameState, a: Action) => GameState
```

This keeps the reducer a pure function of `(state, action)` for `useReducer`, keeps the answer out of persisted state, and makes every test a plain function call — no React, no rendering, no mocks.

**Rules encoded in the reducer, nowhere else:**

- `SUBMIT` is ignored unless all 4 slots are filled.
- `SUBMIT` in a terminal status is a no-op.
- `correctCount === 4` → `won`; otherwise `attempts.length === MAX_ATTEMPTS` → `lost`.
- `PLACE_TILE` onto a filled slot **swaps**; it never silently discards a tile.
- A tile already in a slot cannot be placed into a second slot.

### 8.3 Daily Index — The DST Trap

```ts
const EPOCH = { y: 2026, m: 9, d: 1 };   // 2026-10-01, month is 0-indexed

export function puzzleNumberFor(now: Date): number {
  const a = Date.UTC(EPOCH.y, EPOCH.m, EPOCH.d);
  const b = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate());
  return Math.round((b - a) / 86_400_000) + 1;
}
```

The subtlety worth flagging: we read **local** calendar fields (`getFullYear` / `getMonth` / `getDate`) but do the arithmetic in **UTC**. That normalises away DST entirely — the day count is exact whether or not a 23- or 25-hour day fell in the interval. Subtracting raw timestamps would drift by one puzzle for half the year in every DST-observing timezone, and would do so silently.

A test asserting correct behaviour across a spring-forward boundary is mandatory (§11).

### 8.4 Data Tier

```ts
// data/httpPuzzleRepository.ts
export class HttpPuzzleRepository implements PuzzleRepository {
  constructor(private baseUrl: string) {}      // import.meta.env.BASE_URL — GH Pages subpath

  async load(id: number, date: string): Promise<Puzzle> {
    const res = await fetch(`${this.baseUrl}puzzles/${date}.json`);
    if (!res.ok) throw new PuzzleNotFound(date);
    const { d } = await res.json();
    return validatePuzzle(decode(d, date));    // never trust the payload shape
  }
}
```

`validatePuzzle` is a hand-written runtime guard, ~25 lines. A schema library would be a dependency larger than the thing it validates. It checks:

- [ ] `schemaVersion` matches what this client understands.
- [ ] `solution.length === CHAIN_LENGTH` and `bank.length` is within `10..12`.
- [ ] `bank ⊇ solution`, and `bank` contains **no duplicates** (a duplicate would make two tiles indistinguishable and break `tileId`-as-word, §3.1.1).
- [ ] `id` and `date` agree: `date === EPOCH_DATE + (id - 1)` days.

`LocalStorageProgressStore` wraps **every** access in `try/catch` — Safari private mode throws on write, and a `QuotaExceededError` must degrade to in-memory rather than break the game.

### 8.5 Component Hierarchy

```
<App>                          reads repo + store, owns useReducer, renders states
├── <Header>                   title, puzzle number, stats + help buttons
├── <Board>
│   ├── <AnchorWord fixed>     START
│   ├── <Slot × 4>             empty | filled | selected
│   └── <AnchorWord fixed>     END
├── <WordBank>
│   └── <Tile × 11>            idle | selected | placed
├── <AttemptHistory>           past attempts as "N of 4 correct" rows
├── <SubmitBar>                Check button + <LivesMeter> (3 hearts)
├── <ShareModal>               on win/loss — emoji grid + copy
└── <StatsPanel>               streak, distribution histogram
```

Every component below `<App>` is presentational: props in, callbacks out, no `fetch`, no `localStorage`, no rule logic. Any one of them can be rendered in isolation with literal props.

### 8.6 Accessibility

Not decoration — the count-only feedback model makes most of it nearly free, so there is no excuse for skipping it.

- [ ] Tiles and slots are real `<button>` elements — keyboard and screen-reader support by default.
- [ ] `aria-live="polite"` region announcing *"2 of 4 correct. 2 lives remaining."* after each submit.
- [ ] `LivesMeter` hearts carry a text label (`aria-label="2 of 3 lives remaining"`) — never a bare glyph.
- [ ] Focus moves to the next empty slot after a placement; focus is trapped in the share modal and restored on close.
- [ ] Colour is never the sole signal — the count is stated in text. (Count-only feedback is inherently colourblind-safe.)
- [ ] `prefers-reduced-motion` disables tile and reveal animations.
- [ ] Minimum 44×44 px touch targets.
- [ ] Contrast ratio ≥ 4.5:1 in both light and dark themes.
- [ ] **Keyboard flow is the tap flow.** Tab to a tile → `Enter` selects → Tab to a slot → `Enter` places. Because both are real `<button>`s this needs no extra key handling; `Escape` clears the current selection.

### 8.7 Runtime Edge Cases

Small, individually cheap, and each one is a real bug report if skipped.

| Situation | Behaviour |
|---|---|
| **Midnight passes with the tab open** | The puzzle number is computed once on load, so a tab left open overnight would silently keep serving yesterday's puzzle — and worse, would write progress under the old ID. On `visibilitychange` and `focus`, recompute `puzzleNumberFor(new Date())`; if it changed, finish persisting the old puzzle and offer a **"New puzzle available — play today's"** prompt rather than yanking the board away mid-game. |
| **Fetch fails (offline, flaky network)** | `PuzzleNotFound` vs. a network error are different states. Network error → a retry button and a clear "couldn't load today's puzzle" message. Never an infinite spinner, and never a blank page. |
| **Puzzle genuinely missing** (before launch, or archive exhausted) | `manifest.json` tells the client before it even tries. Friendly "no puzzle today" state; §13 Risk #8. |
| **Two tabs open on the same puzzle** | Last write wins. Deliberately not solved — `localStorage` writes are synchronous and the loser is one stale board. Adding a `storage` listener to reconcile is more code than the bug is worth. `ponytail:` accepted, revisit only if anyone actually reports it. |
| **System clock is wrong / user timezone-hops** | Accepted, exactly as Wordle does. The puzzle number follows local midnight; there is nothing to defend and nothing worth defending. |
| **Player refreshes mid-attempt** | Progress is persisted on every state change, so the board and spent lives restore exactly. This is what `linkage:v1:progress:<id>` exists for. |

---

## 9. Backend: Recommendation & Rationale

### 9.1 Recommendation: No Backend for v1

Everything the game needs — daily puzzle, progress, streaks, stats, sharing — works on a static host with `localStorage`. Adding a database now buys nothing a player can see, and costs an API surface, a deploy target, a secret to rotate, and a thing that can be down at 3am.

**Ship without one.** Add a backend when a concrete feature demands it, and only that feature.

### 9.2 When You Would Actually Need One

| Feature | Needs a backend? |
|---|---|
| Daily puzzle, streaks, personal stats, sharing | **No** — static files + `localStorage` |
| Global stats ("41% solved it in 3") | **Yes** — anonymous write + aggregate read |
| Cross-device sync, accounts, leaderboards | **Yes** — plus auth, which is the real cost |

Global stats is the one with genuine product value: it makes the share text richer and gives players a sense of the crowd. It also needs no accounts and stores no personal data.

### 9.3 Why Not MongoDB Atlas

Atlas M0 is a fine free tier (512 MB, no expiry). The problem is structural, not about quality:

1. **Atlas is a database with no API tier.** You cannot safely call it from a browser — that would mean shipping credentials. So the real architecture is *Atlas + a serverless function*: two services, two dashboards, two failure modes, and a connection-pooling problem (serverless functions and Mongo's connection model are a well-known poor fit without a proxy).
2. **The data model does not want a document store.** Global stats is three counter tables. `INSERT ... ON CONFLICT DO UPDATE SET n = n + 1` is the entire write path. Schema flexibility buys nothing when the schema is `(puzzle_id, attempt_count, n)`.

### 9.4 Recommended When Needed: Cloudflare Workers + D1

| Option | Free tier | Verdict |
|---|---|---|
| **Cloudflare Workers + D1** | 100k req/day, 5 GB storage, 5M row-reads/day. Never sleeps. | ✅ **Recommended** |
| Supabase | 500 MB Postgres, 50k MAU auth | Good — *if* you want accounts. Free projects pause after 7 days idle. |
| Vercel Functions + Neon | 0.5 GB Postgres | Fine. Two vendors instead of one. |
| Turso (libSQL) | 9 GB, 500 DBs | Good; smaller company, still needs a compute tier. |
| MongoDB Atlas M0 | 512 MB | Works, but see §9.3 — strictly more moving parts. |

**Why Workers + D1 wins here:**

- **One service, not two.** The Worker *is* the API and D1 *is* its database, bound directly — no connection string, no pooling, no secret to rotate.
- **SQLite is the right shape** for counter tables, and the query is one line.
- **It does not sleep**, unlike Supabase's free tier — no cold-start on a daily-traffic-spike product.
- **Same edge network as the static assets**, so it stays one deploy target.
- **Zero personal data**, which keeps this a feature and not a compliance surface.

Sketch, for whenever it is wanted:

```sql
CREATE TABLE results (
  puzzle_id  INTEGER NOT NULL,
  attempts   INTEGER NOT NULL,   -- 1..3, or 0 for a loss
  n          INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (puzzle_id, attempts)
);
```

```ts
// POST /api/result  { puzzleId, attempts }   ->  { distribution: number[] }
await env.DB.prepare(
  `INSERT INTO results (puzzle_id, attempts, n) VALUES (?, ?, 1)
   ON CONFLICT (puzzle_id, attempts) DO UPDATE SET n = n + 1`
).bind(puzzleId, attempts).run();
```

Rate-limit by IP hash, cap `attempts` to `0..MAX_ATTEMPTS`, and treat the whole endpoint as best-effort: **if it fails, the game must not notice.** Global stats is a garnish, never a dependency.

> This is deferred work. Nothing in Phases 1–5 depends on it, and the client's `PuzzleRepository` boundary (§4.2) means adopting it later touches the data tier only.

---

## 10. Implementation Phases

### Phase 1 — Data Engine (Python)

*Goal: a queryable concept graph on disk.*

- [ ] **Licensing first** — root `LICENSE`, ConceptNet CC BY-SA 4.0 attribution in `README.md` (§12.2). Cheaper to accept now than after 365 puzzles exist.
- [ ] `engine/pyproject.toml` — pin `networkx`, `wordfreq`, `typer`, `orjson`, `tqdm` to **exact** versions.
- [ ] `data/vocabulary.py` — `wordfreq` top-`VOCAB_FETCH_N` + the §7.1 filter chain + §3.1.1 normalisation.
- [ ] `data/conceptnet.py` — download with SHA-256 verification; **stream-parse**, never load whole.
- [ ] Apply the relation whitelist/blocklist (§7.2).
- [ ] `data/graph_store.py` — build the `networkx.Graph`; save with `pickle.dump(protocol=5)` (**not** `nx.write_gpickle` — removed in NetworkX 3.0).
- [ ] Drop hub words above the 99th degree percentile (§7.3).
- [ ] Stamp provenance (dataset hash, library versions) as graph attributes.
- [ ] `linkage build-graph` CLI command.
- [ ] **Verify:** node/edge counts are sane; spot-check `neighbors('apple')` looks like human association, not noise.

### Phase 2 — Puzzle Generator (Python)

*Goal: `candidates.json`, every entry provably unique.*

- [ ] **`linkage diagnose --samples 200` FIRST** — graph shape, clustering coefficient, weight distribution, survival funnel (§7.9.3). ~60 lines.
- [ ] **Go / no-go:** if yield is under ~3 usable candidates per 1,000 seeds, climb the §7.9.4 remedy ladder *before* writing more generator code.
- [ ] `domain/models.py` — frozen dataclasses.
- [ ] `domain/pathfinder.py` — bidirectional bounded BFS (§7.4), behind the `PathFinder` protocol so §7.9 Tier 5 stays a drop-in swap.
- [ ] Enforce: no direct `S–E` edge, no repeated nodes, chordless, `min(weight) >= 2.0`.
- [ ] `domain/validator.py` — `solve_all` + `is_uniquely_solvable` (§7.5).
- [ ] `domain/distractors.py` — the `DistractorStrategy` protocol + three implementations.
- [ ] `DistractorSelector` — **incremental bank construction** so uniqueness holds by construction (§7.6), plus the stem/substring bank checks.
- [ ] `domain/scoring.py` — `QualityScorer` for review ranking.
- [ ] `data/codec.py` — XOR + base64 encoder; emit `engine/fixtures/codec-fixture.json`.
- [ ] `data/exporters.py` — `candidates.json`, `approved.json`, per-day files, `manifest.json`, **`verification-subgraph.json`** (§7.10).
- [ ] `linkage generate --until-approved 365` — tops up from a new seed offset, skipping decided hashes.
- [ ] `review.py` + `linkage review` — the curation TUI (§7.7).
- [ ] `linkage export --start-date` — hand-pick the launch week, shuffle the rest with a fixed seed, assign dates.
- [ ] **Corpus-level QC at export** (§7.7.1): word-reuse cap, no duplicate `(start, end)`, no repeated chains. **Fail loudly**, never ship quietly.
- [ ] Strip `meta` from the per-day files (§3.1).
- [ ] Run the determinism checklist (§7.8): generate twice, `diff` must be empty.
- [ ] **Verify:** `test_output_invariants.py`, `test_corpus_invariants.py`, and `test_subgraph_completeness.py` all pass **using fixtures only** — no dataset, no pickle.

### Phase 3 — Frontend Scaffold (TypeScript/React)

*Goal: the board renders from a real puzzle file. No interaction yet.*

- [ ] `npm create vite@latest web -- --template react-ts`; add Tailwind.
- [ ] `vite.config.ts` — set `base: '/Linkage/'` for GitHub Pages project sites.
- [ ] `engine/types.ts` and `engine/ports.ts` (interfaces live in the domain tier).
- [ ] ESLint `no-restricted-imports` on `src/engine/**` — no `react`, no DOM, no `fetch`.
- [ ] `data/codec.ts` — the decoder; test it against the Python fixture **before** anything depends on it.
- [ ] `HttpPuzzleRepository` + `validatePuzzle` runtime guard (all four checks, §8.4).
- [ ] `LocalStorageProgressStore` with `try/catch` on every access.
- [ ] Components: `Board`, `Slot`, `WordBank`, `Tile`, `AnchorWord` — presentational only. Display casing via CSS, never stored (§3.1.1).
- [ ] `App.tsx` states: loading / **network error with retry** / **no puzzle today** / ready (§8.7); `main.tsx` as composition root.
- [ ] **Verify:** today's puzzle renders with all 11 tiles; no game logic exists yet.

### Phase 4 — Game Loop & Logic (TypeScript)

*Goal: a fully playable game.*

- [ ] `engine/gameReducer.ts` — `makeGameReducer(puzzle)` (§8.2).
- [ ] Tap-to-place: select → place → remove → swap.
- [ ] `SUBMIT` → `correctCount`, append attempt, resolve `won` / `lost` / continue.
- [ ] `engine/dailyIndex.ts` — DST-safe (§8.3).
- [ ] `engine/stats.ts` — streak and distribution updates.
- [ ] Persist on every state change; restore mid-game on load; prune entries older than 7 days.
- [ ] **Midnight rollover** — recompute the puzzle number on `visibilitychange`/`focus`, prompt rather than yank (§8.7).
- [ ] `AttemptHistory` and `SubmitBar` with `LivesMeter` — 3 hearts, spent ones greyed but still visible.
- [ ] Loss state reveals the full chain.
- [ ] Accessibility pass (§8.6) — `aria-live`, focus management, 44px targets.
- [ ] **Verify:** Vitest covers the reducer, `dailyIndex` across a DST boundary, and stats streak logic.

### Phase 5 — Polish & Share

*Goal: something worth sending to a friend.*

- [ ] `engine/share.ts` — the emoji grid (§2.7); assert it leaks no positional data.
- [ ] `ShareModal` — clipboard write + `execCommand` fallback, with a "Copied!" confirmation.
- [ ] `StatsPanel` — streak, win %, distribution histogram.
- [ ] Tile placement and reveal animations, gated on `prefers-reduced-motion`.
- [ ] Responsive layout: 320 px → desktop; the board must never need a scroll on a phone.
- [ ] Dark mode via Tailwind `dark:`.
- [ ] `HowToPlay` modal, shown once on first visit.
- [ ] Meta/OG tags for link previews; favicon.
- [ ] **Optional:** `@dnd-kit/core` drag, dispatching the same reducer actions — only if playtesting says tap is not enough.
- [ ] **Playtest gate before launch (Risk #11):** ~20 people play puzzles #1–#10 and report their `StatsPanel` numbers. Win rate under ~50% → tune puzzle difficulty, **not** the number of lives, and re-review.
- [ ] **Verify:** Playwright smoke test — load → solve → share modal → clipboard content.

### Phase 6 — Global Stats *(deferred, optional)*

- [ ] Cloudflare Worker + D1 per §9.4. Fire-and-forget from the client; failure must be invisible.

---

## 11. Testing Strategy

Proportionate, not exhaustive. Each test below exists because a specific, plausible failure would otherwise ship silently.

### Python — `pytest`

| Test | Guards against |
|---|---|
| **`test_output_invariants.py`** | **The one that matters.** Loads every shipped puzzle plus `verification-subgraph.json` (§7.10 — so it runs in CI with no dataset), re-runs `solve_all`, asserts **exactly one** solution. Also: no `S–E` edge, `len(solution) == CHAIN_LENGTH`, `10 <= len(bank) <= 12`, `bank ⊇ solution`, no duplicate bank words, no shared stems in a bank, and `date == EPOCH_DATE + (id - 1)` days. If this passes, the game is sound. |
| `test_corpus_invariants.py` | The §7.7.1 corpus-level rules: word reuse ≤ `MAX_WORD_REUSE`, no duplicate `(start, end)` pair in either direction, no repeated solution chain. Individually-valid puzzles that make a bad *year*. |
| `test_subgraph_completeness.py` | That `verification-subgraph.json` is the **induced** subgraph, not just the solution edges — the silent-pass failure mode called out in §7.10. |
| `test_validator.py` | Solver correctness on hand-built toy graphs with known unique / ambiguous / unsolvable answers. |
| `test_pathfinder.py` | Chordless, no repeats, exactly 5 edges, `S–E` rejection. |
| `test_codec.py` | Round-trip, **and** writes `engine/fixtures/codec-fixture.json` for the TS suite. |
| `test_determinism.py` | Generating twice from a fixed seed yields identical bytes. |

> Every test above runs on **committed fixtures only** — no ConceptNet dump, no pickle, no network. That is a hard requirement, not a nicety: CI must be able to run the golden test on every PR (§7.10).

### TypeScript — `vitest`

| Test | Guards against |
|---|---|
| `gameReducer.test.ts` | Place / remove / swap / submit; win at 4 correct; **loss at exactly 3 attempts**; submit blocked when slots are incomplete; no-ops in terminal states. |
| `dailyIndex.test.ts` | **Spring-forward and fall-back boundaries** — the silent off-by-one from §8.3. |
| `codec.test.ts` | Decodes the Python-generated fixture. Catches cross-language UTF-8 and `atob` bugs. |
| `share.test.ts` | Grid shape per outcome; asserts no positional information leaks. |
| `stats.test.ts` | Streak continues on consecutive IDs, resets on a gap. |
| `validatePuzzle.test.ts` | Rejects a bad `schemaVersion`, a short `solution`, duplicate bank words, and an `id`/`date` mismatch (§8.4). |

### End-to-End — `playwright`

One test, not a suite: load the page, solve today's puzzle, assert the share modal opens with the expected grid.

---

## 12. CI/CD & Deployment

**GitHub is already connected:** `origin → https://github.com/TechGenius-Karan/Linkage.git`, with `gh` authenticated as `TechGenius-Karan` (scopes: `repo`, `workflow`, `read:org`, `gist`). No setup needed.

**Host: GitHub Pages.** Free, already where the repo lives, and the client is fully static. Vercel is a drop-in alternative if you later want preview deploys per PR.

```
.github/workflows/test.yml     on: pull_request   -> pytest + vitest + tsc --noEmit
.github/workflows/deploy.yml   on: push to main   -> npm ci && npm run build -> actions/deploy-pages
```

**Deployment gotchas, all of which bite silently:**

- `vite.config.ts` needs `base: '/Linkage/'` for a project site. Without it every asset 404s on Pages but works perfectly in local dev.
- All puzzle fetches must go through `import.meta.env.BASE_URL` — never a hardcoded `/puzzles/...`.
- `web/public/puzzles/**` is **committed**, not generated in CI. The engine needs a 1.2 GB dataset; CI must never touch it. Regenerating puzzles is a deliberate local action followed by a commit. CI still runs the golden test — on `engine/fixtures/verification-subgraph.json`, not on the graph (§7.10).
- `engine/fixtures/**` is committed but **must never be copied into the published output**. It is a plaintext answer key.
- `.gitignore` must cover `data/raw/`, `data/*.gpickle`, `node_modules/`, `dist/`, `engine/candidates.json`, `engine/approved.json`.

**Branching:** `main` is deployable at all times. Feature branches per phase (`phase-1-data-engine`, …), squash-merged via PR so `test.yml` gates every change.

### 12.1 Fixing a Single Bad Puzzle After Launch

A puzzle will eventually ship that is broken, unfair, or unfortunate. **Regenerating the whole archive is not an option** — the seed shuffle would reassign every date, changing puzzle numbers people have already shared.

The per-day file layout (§3.2) makes this a non-event:

1. Edit or replace `web/public/puzzles/<date>.json` **only**. Every other day is untouched, and `id` ordering is preserved.
2. Re-run `linkage export --verify-only` to refresh `verification-subgraph.json` and re-run the golden test.
3. Commit and push. GitHub Pages redeploys; the CDN cache expires within the day.

Players mid-game on that date keep their local progress, and the reducer validates against whatever it fetched — so the worst case is one person seeing a changed board on refresh. This is a genuine benefit of per-day files that the single-`puzzles.json` design would not have given us.

### 12.2 Licensing & Attribution

**This is a legal requirement, not a courtesy.**

| Asset | Licence | What we must do |
|---|---|---|
| **ConceptNet 5.7** | **CC BY-SA 4.0** | **Attribute in the app and the repo.** ShareAlike plausibly reaches the derived puzzle data, so `web/public/puzzles/**` and `engine/fixtures/**` carry a CC BY-SA 4.0 notice. |
| `wordfreq` | MIT (bundled data has its own upstream terms) | Standard dependency attribution. |
| Our own code | Choose one — MIT is the obvious default | Add `LICENSE` at the repo root. |

Actions:

- [ ] `README.md` credits ConceptNet with a link to `conceptnet.io` and the CC BY-SA 4.0 deed.
- [ ] The in-app **About / HowToPlay** modal carries the same attribution — a player-facing surface, not just a repo file.
- [ ] `web/public/puzzles/LICENSE.txt` states CC BY-SA 4.0 for the derived data.
- [ ] Root `LICENSE` for the source code.

> Worth deciding **before** Phase 1, not after 365 puzzles are generated: ShareAlike on the derived dataset is much easier to accept up front than to discover late.

---

## 13. Risk Register

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| 1 | **Generated puzzles are technically valid but not fun** | High | Fatal to the product | Hub-word removal (§7.3), chordless paths (§7.4), weight gating, tempting distractors (§7.6), and a human review gate (§7.7). This is the top risk and gets the most machinery. |
| 2 | ~~**Yield collapse — constraint stack rejects nearly every path**~~ | ~~High~~ **CLOSED** | — | **Measured twice in Phase 1 (§7.9.5): 4.57M usable paths per 1,000 seeds against a threshold of 3.** Chordless costs ~32%, not the predicted ~93%. No remedy tier needed for yield. The ladder in §7.9.4 stays documented for any future tightening of the constraint set. |
| 3 | **Cross-language codec mismatch** | Medium | Client cannot read any puzzle | Python emits a fixture; the TS test decodes it. Wired in Phase 3 **before** anything depends on the codec. |
| 4 | **`nx.write_gpickle` removed in NetworkX 3.0** | Certain | Phase 1 fails on first run | Documented in §7.2. Use `pickle.dump` directly. |
| 5 | **`wordfreq` data drift between versions** | Medium | Vocabulary silently changes; puzzles unreproducible | Pin exactly; record the version in graph metadata; `generate` refuses a metadata mismatch. |
| 6 | **DST off-by-one in the daily index** | High if unguarded | Wrong puzzle for half the year, in half the world | UTC-normalised date arithmetic (§8.3) + a boundary test. |
| 7 | **GH Pages `base` path misconfigured** | High | Blank page in production, works locally | Called out in §12; caught by the Playwright test running against the built output. |
| 8 | **Puzzle archive runs dry after 365 days** | Certain, eventually | Game stops | `manifest.json` lets the client show a graceful message. Re-run `generate` + `review` before the archive expires. |
| 9 | **Spoilers via DevTools** | Low | Minor | Per-day files + obfuscation (§3.2). Accepted residual risk — Wordle shipped its whole word list. |
| 10 | **Offensive or unfortunate word chains reach players** | Low | Reputational | Profanity blocklist in §7.1 plus the human review gate — a person reads every shipped puzzle. |
| 11 | **Win rate too low under 3 lives + count-only feedback** | Medium | Kills the share loop — nobody posts `X/3` | **Instrument first:** we ship no analytics (§14), so measure by *manual playtest* — ~20 people play puzzles #1–#10 and report the numbers from their own `StatsPanel`. That sample easily separates a 30% win rate from a 70% one, which is all the resolution this decision needs. If under ~50%, tune puzzle difficulty (distractor temptingness, `MIN_EDGE_WEIGHT`, review strictness); a fourth heart is the last resort (§2.5.1). |
| 12 | **Golden test cannot run in CI** (needs the 1.2 GB dataset) | **Was certain** | The one test the game rests on never runs on a PR | **Resolved by design** — `verification-subgraph.json` (§7.10). CI runs on committed fixtures only. |
| 13 | **ConceptNet CC BY-SA 4.0 attribution / ShareAlike** | Certain | Licence violation on the derived puzzle data | Attribution in README, in-app About modal, and `puzzles/LICENSE.txt` (§12.2). Decide **before** Phase 1. |
| 14 | **Word repetition makes the year feel small** | High if unguarded | `gravity` in forty puzzles; players notice fast | `MAX_WORD_REUSE = 3` cap, no duplicate `(start, end)` pairs, no repeated chains — enforced at export, `test_corpus_invariants.py` (§7.7.1). |
| 15 | **Acceptance rate lower than assumed; fewer than 365 approved** | Medium | Cannot fill a year | `generate --until-approved 365` tops up from a new seed offset, skipping already-decided content hashes (§7.7). Never assume one pass suffices. |
| 16 | **Not enough uniqueness-safe distractors for a puzzle** | Medium | Candidate discarded, yield drops further | Fall back to `BANK_SIZE = 10` (spec allows 10–12) before discarding the candidate (§7.9.4 Tier 4). |
| 17 | **Midnight passes with the tab open** | Certain for some players | Progress written under yesterday's ID; stale board | Recompute the puzzle number on `visibilitychange`/`focus`; prompt rather than yank the board (§8.7). |
| 18 | **Same-stem or overlapping words in one bank** | Medium | Looks sloppy; `moon` next to `moons` | Porter-stem comparison plus a substring check across the bank at selection time (§7.6). |
| 19 | ~~**Degree-percentile pruning is deleting good puzzle words**~~ | ~~Confirmed~~ **RESOLVED** | — | **Automatic pruning removed; the curated `GENERIC_HUBS` list does this job** (§7.3). All 75 words restored, `animal` through `bridge`. Degree is the wrong signal — it measures connectedness, not genericness. `build-graph` still reports the top 40 by degree as candidates for the curated list. |
| 20 | **Generator enumerates paths exhaustively and never finishes** | High if unguarded | `generate` runs for hours producing candidates nobody will review | 25 seeds yielded 33M paths (§7.9.5). The generator needs per-seed budgets and early termination, not exhaustive enumeration. Design constraint for Phase 2. |

---

## 14. Explicitly Out of Scope

Listed so they are not accidentally built, and so the reasoning survives:

| Not building | Add when |
|---|---|
| User accounts / auth | Cross-device sync is actually requested. Bring Supabase then, not Workers. |
| Cross-device sync | Above. |
| Puzzle archive / play past dailies | Post-launch. Requires a date picker and a rethink of streaks. |
| Difficulty levels | We do not yet know what "hard" means empirically. Ship one difficulty, measure the distribution, then decide. |
| Hint system | Retention data says players are quitting mid-puzzle. |
| Server-rendered / native app | Never, for this product. Static is the whole point. |
| i18n | ConceptNet is multilingual, so it is *possible* — but each language needs its own vocabulary, tuning, and curation pass. That is a second product. |
| Redux / Zustand / TanStack Query | The state is 4 slots and an array; one `fetch` runs once per day. |
| Runtime schema library (zod) | The 20-line hand-written guard in §8.4 is smaller than the dependency. |
| Analytics | A real question about player behaviour needs answering, and privacy implications are considered first. |
| PWA / offline mode | Players ask for it. The whole app is ~50 KB and loads instantly anyway. |

---

## 15. Problem → Solution Index

Completeness check: **every problem named anywhere in this document, and where its solution lives.** If a row has no solution, it does not belong in the plan.

### Puzzle quality

| Problem | Solution | § |
|---|---|---|
| Hub words route every path through `thing`/`object` | Curated `GENERIC_HUBS` blocklist at the vocabulary stage. Degree pruning was tried, measured, and **removed** — it deleted good words (Risk #19) | §7.3 |
| Morphological edges (`run → running`) are not insights | Relation blocklist: `FormOf`, `DerivedFrom`, `EtymologicallyRelatedTo` | §7.2 |
| Synonyms/antonyms make a leap too small or confusing | Relation blocklist | §7.2 |
| Chains feel arbitrary — a rung could be skipped | Chordless constraint; every rung load-bearing | §7.4 |
| One weak link makes a chain feel unfair | Gate on the path's **minimum** edge weight, not the mean | §7.4 |
| Distractors nobody would pick add no difficulty | Three ranked strategies scored by *temptingness* | §7.6 |
| `moon` and `moons` in the same bank | Porter-stem + substring check across the bank | §7.6 |
| A decoy echoing an **endpoint** (`branch` under `BRANCHES`) | The same checks, extended to include start and end — the endpoints are on screen all game | §7.6 |
| Scorer ranks vague chains above elegant ones | `specificity` component: edge weight measures how *obvious* a link is, not how *good* | §7.7.2 |
| Generator enumerates forever | Per-pair path budget and a pair budget; one puzzle per endpoint pair | §7.4, Risk #20 |
| Algorithmically valid ≠ fun | Human review gate over a generated surplus | §7.7 |
| A word appears in forty puzzles; the year feels small | `MAX_WORD_REUSE = 3`, enforced at export | §7.7.1 |
| Duplicate `(start, end)` pairs or repeated chains | Corpus-level QC, fails export loudly | §7.7.1 |
| A brutal puzzle #1 loses players on day one | Launch week hand-picked from the quality ranking | §7.7.1 |
| Offensive words reach players | Profanity blocklist + a human reads every shipped puzzle | §7.1, §7.7 |

### Generation & correctness

| Problem | Solution | § |
|---|---|---|
| **Yield collapse — constraints reject nearly every path** | Measure with `linkage diagnose`, then a six-tier remedy ladder | **§7.9** |
| Low yield silently *biases* the puzzle set | Named explicitly as the failure mode to fear; the funnel exposes it before generation | §7.9.2 |
| Alternate solutions make a puzzle ambiguous | Incremental bank construction — uniqueness by construction, not by hope | §7.6 |
| Reorderings of the solution words also solve it | Chordless proof; minimal ban set preserves it exactly | §7.4, §7.9.4 T2 |
| Not enough uniqueness-safe distractors | Fall back to `BANK_SIZE = 10` before discarding the candidate | §7.9.4 T4 |
| Fewer than 365 candidates survive review | `generate --until-approved 365`, topping up from a new seed offset | §7.7 |
| Output not reproducible | Determinism checklist: seeded RNG, sorted iteration, pinned versions, hashed dataset | §7.8 |
| `wordfreq` data drift changes the vocabulary silently | Exact pin + version recorded in graph metadata; `generate` refuses a mismatch | §7.1, §7.2 |
| `nx.write_gpickle` removed in NetworkX 3.0 | `pickle.dump(protocol=5)` directly | §7.2 |
| BFS solves a harder problem than we have | `PathFinder` behind a protocol; constructive growth is a drop-in swap | §7.9.4 T5 |

### Client

| Problem | Solution | § |
|---|---|---|
| DST shifts the puzzle number by one for half the year | Local calendar fields, UTC arithmetic, plus a boundary test | §8.3 |
| Midnight passes with the tab open | Recompute on `visibilitychange`/`focus`; prompt, don't yank | §8.7 |
| Network failure shows an infinite spinner | Distinct network-error state with retry; `manifest.json` pre-empts a 404 | §8.7, §3.3 |
| `localStorage` throws in Safari private mode | `try/catch` on every access, degrade to in-memory | §2.8, §8.4 |
| Two tabs diverge | Last write wins — accepted, documented, not solved | §8.7 |
| Malformed payload crashes the client | `validatePuzzle` runtime guard, four checks | §8.4 |
| The solution leaks via React DevTools / `localStorage` | Reducer curried over the puzzle; the answer never enters `GameState` | §8.2 |
| Drag-and-drop is dead on touch devices | Tap-to-place in v1; dnd-kit later on the same actions | §2.4 |
| Colour-only feedback excludes colourblind players | Count-only feedback is a number stated in text | §2.5 |
| GH Pages `base` path breaks every asset | `base: '/Linkage/'` + `import.meta.env.BASE_URL` everywhere | §12 |

### Cross-cutting

| Problem | Solution | § |
|---|---|---|
| **Golden test cannot run in CI without a 1.2 GB dataset** | Export the induced `verification-subgraph.json`; CI runs on fixtures only | **§7.10** |
| A subgraph of only solution edges makes the test vacuously pass | `test_subgraph_completeness.py` asserts it is the *induced* subgraph | §7.10, §11 |
| Codec disagrees between Python and TypeScript | Python emits a fixture; the TS suite decodes it, wired before anything depends on it | §3.2, §11 |
| Spoilers via DevTools | Per-day files + XOR/base64; accepted residual risk | §3.2 |
| The verification subgraph is a plaintext answer key | Lives in `engine/fixtures/`, never in `web/public/` | §7.10, §12 |
| ConceptNet CC BY-SA 4.0 attribution & ShareAlike | Attribution in README, in-app About, and `puzzles/LICENSE.txt` — decided before Phase 1 | §12.2 |
| One bad puzzle ships; regenerating would reshuffle every date | Per-day files — replace one file, re-verify, push | §12.1 |
| The archive runs dry after 365 days | `manifest.json` drives a graceful message; regenerate before it expires | §3.3 |
| Win rate too low to sustain sharing, with no analytics to measure it | Manual playtest, ~20 people on puzzles #1–#10, reporting their own `StatsPanel` | §2.5.1, Risk #11 |

---

## Appendix A — Tunable Constants

All of these live in one file per side (`engine/config.py`, `web/src/engine/constants.ts`). Changing gameplay should never mean hunting through source.

| Constant | Default | Notes |
|---|---|---|
| `VOCAB_FETCH_N` | 12000 | How many frequency-ranked words `wordfreq` returns before filtering. |
| `VOCAB_TARGET` | 8000 | How many survive the §7.1 filter chain. Per spec. |
| `VOCAB_MIN_RANK` | 500 | Skips the too-generic head of the frequency list. |
| `WORD_MIN_LEN` / `WORD_MAX_LEN` | 3 / 12 | Longer words overflow a tile at 320 px (§3.1.1). |
| `CHAIN_LENGTH` | 4 | Intermediate words. Structural — changing it touches the solver and the UI. |
| `BANK_SIZE` | 11 | Spec allows 10–12. Falls back to 10 when safe distractors run short (Risk #16). |
| `MAX_ATTEMPTS` | 3 | Three lives. **Tune by playtest** (Risk #11). |
| `MIN_EDGE_WEIGHT` | 2.0 | Gate on the path's *weakest* edge. §7.9.4 Tier 1 may soften this to a rank. |
| `BFS_TOP_K` | 40 | Neighbours kept per frontier expansion. |
| `HUB_PERCENTILE` | `None` | **Automatic degree pruning is off** — the curated `GENERIC_HUBS` list does this job (§7.3, Risk #19). Set a float to re-enable; the machinery is kept and tested. |
| `HUB_REPORT_TOP_N` | 40 | Highest-degree words printed after a build, as curated-list candidates. |
| `ENFORCE_CHORDLESS` | `full` | `full` \| `minimal` \| `off` — see §7.9.4 Tier 2. `minimal` keeps the uniqueness proof intact. |
| `MAX_WORD_REUSE` | 3 | Times any word may appear across the whole year (§7.7.1). |
| `MIN_ENDPOINT_DEGREE` | 5 | A degree-1 endpoint has one possible neighbour and makes a forced rung. |
| `MAX_PATHS_PER_PAIR` | 8 | Per-pair search budget. Risk #20 -- 25 seeds once produced 33M paths. |
| `DISTRACTOR_POOL_SIZE` | 120 | Candidates each strategy proposes before ranking. |
| `BANK_SIZE_MIN` | 10 | Fallback when too few uniqueness-safe distractors exist (Risk #16). |
| `HUB_DEGREE` (scoring) | 100 | Degree at which a step counts as fully generic (§7.7.2). |
| `TARGET_APPROVED` | 365 | `generate --until-approved` tops up until this many are accepted. |
| `LAUNCH_WEEK_SIZE` | 7 | Hand-picked easy puzzles at the front of the archive (§7.7.1). |
| `SEED` | 20261001 | Any change re-rolls every puzzle. |
| `EPOCH_DATE` | `2026-10-01` | Puzzle #1. Must match `manifest.json` and every `date` field. |

---

## Appendix B — Decision Log

| Decision | Chosen | Rejected | Rationale |
|---|---|---|---|
| Feedback model | **Count-only** (`X of 4`) | Positional green/grey; instant snap-back | Preserves semantic reasoning over deduction; makes the share grid spoiler-free for free. |
| Attempts | **3, framed as lives** (`♥ ♥ ♥`) | 6 attempts | Hearts read as stakes, a counter reads as a budget. 3 tries makes deduction impossible by design, forcing semantic commitment. Watch win rate (Risk #11). |
| Pathfinding | **Bidirectional BFS**, `PathFinder` behind a protocol | Committing to BFS outright | Spec-mandated and gives diverse endpoints — but §7.9 Tier 5 may require constructive growth, so the seam stays open. |
| Interaction | **Tap-to-place**, drag in Phase 5 | dnd-kit from the start | HTML5 DnD is dead on touch. Zero deps, keyboard-accessible, mobile-native. |
| Curation | **Generated surplus + human review**, topping up until 365 are approved | Fully automated 365 | ConceptNet noise means valid ≠ fun. Roughly two evenings buys the difference. |
| Puzzle delivery | **Per-day files + XOR/base64** | Single plain `puzzles.json` | ~1 KB vs ~400 KB, and stops casual spoilers. |
| Backend | **None for v1**; Workers + D1 later | MongoDB Atlas | Atlas has no API tier, so it is Atlas *plus* a function. D1 is one service, SQLite fits counter tables, and it does not sleep. |
| Host | **GitHub Pages** | Vercel | Repo is already there; the client is fully static. |
| Client state | **`useReducer`** | Redux / Zustand | 4 slots and an array. The library would exceed the state it manages. |
| Graph library | **NetworkX** | Neo4j, igraph | Per spec. Offline, one-shot, in-memory — a graph *database* solves a problem we do not have. |
| Uniqueness | **Incremental bank construction** | Generate-then-reject | Uniqueness becomes an invariant, not a hoped-for property. Far higher yield. |
| CI verification | **Induced `verification-subgraph.json`** | Skipping the golden test in CI; building the graph in CI | ~300 KB fixture makes the most important test run on every PR with no dataset. |
| Answer-key fixture location | **`engine/fixtures/`** | `web/public/puzzles/` | It is unobfuscated and would undo §3.2 if served. |
| Puzzle repetition control | **Corpus-level QC at export** | Per-puzzle checks only | 365 individually-good puzzles can still make a bad year. |
| Hub-word removal | **Curated `GENERIC_HUBS` list only** | P99 degree pruning; P99.9 as a compromise | Measured in Phase 1: degree tracks connectedness, genericness is what ruins a puzzle, and they are different properties. P99 deleted `animal`, `bird`, `bridge`. A threshold cannot make this call; a person can, and only a handful of words need it. The ranking is still *reported* as curation input. |
| Uniqueness solver | **`itertools.permutations`, per the plan** | Hand-rolled pruned DFS | Costed it before optimising: the incremental bank build runs ~57k permutations per puzzle, about 60ms. A DFS would be faster and buy nothing. A fuzz test checks it against the plan's reference code on 40 random graphs. |
| Chordless mode | **Boolean `full` / `off`** | The three-way `full`/`minimal`/`off` in §7.9.4 Tier 2 | Tier 2 exists to buy yield. Phase 1 measured chordless at ~32% cost, not the feared ~93%, so `minimal` is unimplemented — YAGNI, and the plan's own guidance says drop to it only if diagnose demands it. |
| Scorer emphasis | **`specificity` at 0.30, strength cut to 0.30 combined** | Edge strength dominant | Reading 900 real candidates: strength-led scoring put mush at 0.91 and an elegant chain dead last at 0.57 (§7.7.2). |

---

## Appendix C — Command Reference

```bash
# ---- Engine (Python) — run locally, roughly monthly ----
cd engine && pip install -e .

linkage build-graph                     # ~20 min, needs the 1.2 GB ConceptNet dump
linkage diagnose --samples 200          # yield funnel — RUN THIS BEFORE GENERATING (§7.9.3)
linkage generate --until-approved 365   # ranked candidates.json; tops up across runs
linkage review                          # human accept/reject -> approved.json
linkage export --start-date 2026-10-01  # per-day files + manifest + verification subgraph
linkage export --verify-only            # refresh the subgraph and re-run invariants

pytest                                  # fixtures only — no dataset needed

# ---- Client (TypeScript) ----
cd web && npm ci

npm run dev                             # Vite dev server
npm test                                # vitest
npx playwright test                     # e2e smoke
npm run build                           # -> dist/, deployed by GitHub Actions
```

**Order of operations for a fresh archive:** `build-graph` → `diagnose` → *(climb the §7.9.4 ladder if yield is short)* → `generate` → `review` → `export` → `pytest` → commit.
