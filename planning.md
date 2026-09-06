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
7. [Deep Dive — Python Generation Engine](docs/engine.md)  ·  *moved*
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

**Start here:** §2 and §3 are the product and the contract — everything else serves them.
§15 indexes every problem in this document against the section that solves it.

**Companion documents:** [`docs/engine.md`](docs/engine.md) holds §7, the generation
internals. [`docs/design.md`](docs/design.md) holds the visual language — palette,
type, spacing, motion — which §8 deliberately says nothing about.

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

### 2.4 Interaction Model — Tap to Place, Slide to Reorder *(decided)*

Two gestures, each owning one job. **Tap fills the ladder from the bank; slide
rearranges what is already in it.**

**Placing — tap, unchanged from the original design:**

1. Tap a bank tile → it enters `selected` state.
2. Tap an empty slot → the tile moves in.
3. Tap a *filled* slot while holding a tile → the two **swap**.

**Reordering — slide:**

4. Drag a filled slot up or down → it **exchanges** with the slot it lands on.

**Removing — double-tap:**

5. Double-tap a filled slot → the tile returns to the bank.

> ⚠️ **Consequence: a single tap on a filled slot while holding nothing now
> does nothing.** That gesture used to be "return to bank"; moving removal to
> double-tap leaves it with no job, and a tap that does nothing reads as
> broken. This is the accepted cost of making removal deliberate — accidental
> single taps were destroying placements. Revisit if playtesting shows people
> tapping and getting confused.

**Why double-tap for removal:** a single tap is trivially easy to fire by
accident on a phone, and losing a placement you were mid-way through reasoning
about is the most annoying thing the board can do to you. Removal should cost
a deliberate second tap.

> ⚠️ **`touch-action: manipulation` is mandatory on slots and tiles.** Mobile
> browsers interpret a double-tap as zoom, so without it the removal gesture
> zooms the board instead of clearing a slot. This is not a nicety — it makes
> the gesture unusable on the primary platform.

#### Why a hand-rolled slide, not a drag library

§8.5's `Slot` reorder is **four items in a fixed-height vertical column**,
which is the easiest possible case for a drag: track the pointer's Y delta,
divide by row height, clamp to `0..3`. That is Pointer Events and roughly
seventy lines — `pointerdown` / `pointermove` / `pointerup` are already unified
across mouse, touch and pen, which is the whole reason HTML5 drag-and-drop was
rejected here in the first place (it does not fire on touch).

`@dnd-kit` remains **out**. It exists to solve sortable lists across arbitrary
containers with collision detection and keyboard sensors; we have one container
of four rows. The bank → slot direction stays tap-only, so the library would be
earning its bundle size on a single interaction.

**The reducer never learns that dragging exists.** The gesture is presentation;
it dispatches `MOVE_TILE { from, to }` and nothing else. Tier boundary intact
(§4.2), and the reducer stays testable as a plain function call.

#### Keyboard and screen-reader equivalents *(not optional)*

Double-tap and slide are both pointer gestures with no keyboard analogue, and
§8.6 is a commitment rather than an aspiration. Every gesture therefore has a
key that does the same thing to a focused slot:

| Gesture | Key on a focused slot | Action |
|---|---|---|
| Tap bank tile, tap slot | `Enter` / `Space` | Place the held tile |
| Slide up / down | `↑` / `↓` | Exchange with the slot above / below |
| Double-tap | `Backspace` / `Delete` | Return the tile to the bank |
| — | `Escape` | Clear the current selection |

Because slots and tiles are real `<button>`s, this is key handling on one
component, not a parallel interaction model.

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

### 2.5.1 Lives, Not Attempts *(shape decided; count open)*

`MAX_ATTEMPTS` is presented to the player as **lives** (`♥ ♥ ♥ ♥ ♥`), never as an attempt counter.

The reframe is the point. "3 of 6 attempts used" reads as a budget to spend; **hearts read as stakes**. It changes how a player approaches the board — from probing to committing. Spent hearts stay visible but greyed, so the cost is felt rather than read.

> ⚠️ **The count itself is deliberately unsettled.** Three was the original figure and proved too harsh on reflection; five and six are both defensible. It is a single client-side constant, it blocks nothing in the generator, and fixing it now means fixing it without the one measurement that actually decides it.
>
> **Dev builds run at `MAX_ATTEMPTS = 5`** so the lives meter, the share grid and the loss state all have something concrete to render. The real number is settled at the Phase 5 playtest gate (Risk #11), from observed win rate.

**The tension to hold while deciding:**

- **Too few and the win rate collapses.** Wordle's ~95% win rate is a large part of why people share it — nobody posts a failure. Count-only feedback plus a short life count is a genuinely hard combination, and below roughly 50% the share loop dies quietly.
- **Too many and the feedback becomes an exploit.** With `P(11, 4) = 7,920` arrangements and ~2.3 bits of feedback per guess, a small budget cannot be deduced through — which is precisely what pushes the weight back onto semantic reasoning. Given enough guesses, mechanical permuting becomes viable, which §2.5.2 identifies as the thing that inverts what the game rewards.

Five sits between those. That is why dev builds use it, and it is a starting position rather than a verdict.

**If the win rate does come in low, the first lever is puzzle difficulty, not more hearts.** In order: reduce distractor temptingness (§7.6), raise `MIN_EDGE_WEIGHT` so chains read more obviously, tighten the review gate. Adding a heart is the last resort — the life count becomes part of the game's identity the moment it ships, and difficulty is the softer knob.

**Loss condition:** all lives spent → `lost`. The full solution chain is then revealed.

### 2.5.2 Open question — time instead of lives?

**Proposal:** drop the fail state entirely and score on *time to solve*, comparing and recording players' times.

**Verdict: not as a replacement for lives. Worth having as a secondary stat.** The reasoning, so the decision can be revisited with the argument intact rather than re-litigated from scratch:

1. **Without scarcity, the feedback becomes an exploit.** Count-only feedback works *because* guesses are scarce. Make them free and the optimal strategy is mechanical probing — permute tiles, read the count, converge. The game would then reward *clicking speed*, not insight. This is the decisive objection: it does not merely change the challenge, it inverts what the game rewards.

2. **A timer fights the core design.** §1.3's north star is the "aha" — and an aha is a *pause*. You stare, turn the idea over, and it clicks. Insight problems are measurably hindered by time pressure; Linkage is an insight problem by construction. A clock converts a contemplative game into a reflex game.

3. **You would have to cap attempts anyway** — or add a time penalty per wrong guess — at which point lives have been reinvented with extra steps.

4. **Comparison needs a backend.** Personal-best timing is trivial and local. "Compared and measured" against other players means the Workers + D1 tier in §9, which v1 deliberately does not have.

5. **It punishes how dailies are actually played** — on a commute, in a queue, half-distracted, phone down mid-puzzle.

**What does work:** record elapsed time as a *stat*, shown on the win screen and in `StatsPanel`, with lives still deciding win/loss. Cheap, local, no backend, and it gives the competitive hook without letting speed override thinking. If a leaderboard is ever wanted, time-as-tiebreaker among equal-attempt solves is the natural shape.

**Deferred to Phase 4.** Nothing here blocks puzzle generation.

### 2.6 The Daily Cycle

- One puzzle per day, resetting at **midnight local time**.
- `puzzleNumber = daysBetween(EPOCH_DATE, todayLocal)`.
- Computed with **date-only arithmetic** (`new Date(y, m, d)` for both endpoints), never raw millisecond subtraction — otherwise DST transitions shift the puzzle by one for half the year. See §8.3.
- Timezone-hopping to reach tomorrow's puzzle early is accepted, exactly as Wordle does.

### 2.7 Sharing

Wordle-shaped and spoiler-free. One row per attempt; the number of filled squares equals `correctCount`.

```
Linkage #142  3/5

[Y][Y][ ][ ]        (rendered with emoji: yellow / white / green)
[Y][Y][Y][ ]
[G][G][G][G]

https://techgenius-karan.github.io/Linkage/
```

- 🟨 — one correct placement in that attempt.
- ⬜ — one incorrect placement.
- 🟩 — the winning row.
- A loss renders `X/N` with every row shown.
- At most `MAX_ATTEMPTS` rows — at 5 the grid still fits any post without wrapping.

Because squares are **left-packed rather than positional**, the grid leaks *zero* information about which slots were right. A friend seeing your grid learns your struggle, not the answer. This falls out naturally from the count-only feedback model — the two decisions reinforce each other.

Copy via `navigator.clipboard.writeText`, with a hidden `<textarea>` + `document.execCommand('copy')` fallback for older iOS Safari.

### 2.8 Persistence

`localStorage`, versioned keys, single-device.

| Key | Contents |
|---|---|
| `linkage:v1:progress:<id>` | In-flight board state for puzzle `<id>` — survives a mid-game refresh. |
| `linkage:v1:stats` | `gamesPlayed`, `wins`, `currentStreak`, `maxStreak`, `distribution[1..MAX_ATTEMPTS]`, `lastCompletedId` |

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

**Moved to [`docs/engine.md`](docs/engine.md).**

Vocabulary, graph construction, the hub problem, pathfinding, the solver,
distractors, human curation, the yield measurements, and the verification
subgraph. Roughly 630 lines that only the engine needs. Section numbers are
unchanged, so every §7.x reference in this document resolves there.
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
  | { type: 'PLACE_TILE';  slot: number }         // places the currently selected tile
  | { type: 'MOVE_TILE';   from: number; to: number }  // slide / arrow keys — exchange
  | { type: 'REMOVE_TILE'; slot: number }         // double-tap / Backspace
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
- `MOVE_TILE` **exchanges** the two slots' contents, including when the
  destination is empty (an exchange with nothing is a move). `from === to` is a
  no-op, and both indices are bounds-checked — a gesture that reports a bad
  index must not corrupt the board.
- `MOVE_TILE` and `REMOVE_TILE` do **not** clear `selectedTile`. Reordering the
  ladder while holding a bank tile is a legitimate thing to want to do.

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
├── <Header>
│   ├── title + puzzle number
│   └── <IconButton × 4>       hint · stats · how-to-play · settings
├── <Board>                    owns the slide gesture; dispatches MOVE_TILE
│   ├── <AnchorWord fixed>     START
│   ├── <Slot × 4>             empty | filled | dragging
│   └── <AnchorWord fixed>     END
├── <WordBank>
│   └── <Tile × 11>            idle | selected | placed
├── <AttemptHistory>           past attempts as "N of 4 correct" rows
├── <SubmitBar>                Check button + <LivesMeter>
├── <ShareModal>               on win/loss — emoji grid + copy
├── <StatsPanel>               streak, distribution histogram
├── <HowToPlay>                also opens from the header, not first visit only
└── <SettingsPanel>            contents TBD (§8.5.1)
```

Every component below `<App>` is presentational: props in, callbacks out, no `fetch`, no `localStorage`, no rule logic. Any one of them can be rendered in isolation with literal props.

**The slide gesture lives on `<Board>`, not `<Slot>`.** A slot cannot know
which slot it was dragged onto; only their common parent can. `<Board>` owns
the pointer handlers and the row geometry, and each `<Slot>` receives a
`dragOffset` prop plus its state. This keeps `<Slot>` a pure function of props
— renderable in isolation with literal values, same as everything else here.

### 8.5.1 The four header buttons

| Button | Status | Notes |
|---|---|---|
| **How to play** | Planned (§ Phase 5) | Was "shown once on first visit". Now also reachable any time, which is strictly better — people forget the rules by day three. |
| **Statistics** | Planned (`StatsPanel`) | Streak, win %, distribution. No change. |
| **Settings** | **New — one agreed item** | **Dark mode**, as a control rather than an OS follow (`docs/design.md` 2.1, which previously ruled this out). It brings two costs: the choice must persist, and `data-theme` must land on `<html>` before first paint or every load flashes the wrong background — so an inline script in `index.html`, not React. Other candidates still open: reduced-motion override, hard reset of local stats. |
| **Hint** | **New — reverses a documented decision** | See below. |

> ⚠️ **A hint system is currently listed in §14 as explicitly out of scope**,
> gated on "retention data says players are quitting mid-puzzle". Adding it is
> a product call, and a legitimate one — but it is not a button, it is a
> mechanic, and three questions have to be answered before Phase 4 can encode
> it:
>
> 1. **What does a hint reveal?** One solution word in place? A narrowing of
>    the bank? Which of your placed tiles is wrong — bearing in mind that last
>    one hands over positional information the whole feedback model (§2.5) is
>    built to withhold.
> 2. **What does it cost?** Nothing, a life, or the win. If it is free, the
>    optimal strategy is to take it, and the puzzle is a 3-word puzzle.
> 3. **What does the share grid say?** A `3/5` earned with two hints is not
>    the same result as one earned without, and the share text is the growth
>    channel (§1.4). Either it is marked or the grid quietly lies.
>
> None of this blocks Phase 3 — the button renders and does nothing. It must
> be settled before Phase 4.

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
- [ ] **Every pointer gesture has a key** (§2.4): `↑`/`↓` exchange slots, `Backspace`/`Delete` returns a tile to the bank, `Escape` clears the selection. A gesture with no keyboard path is a feature half the plan's own accessibility section forbids.
- [ ] `touch-action: manipulation` on slots and tiles, so double-tap removes rather than zooms.
- [ ] A slot being dragged carries `aria-grabbed` and the live region announces the exchange (*"moved to slot 3"*) — the visual motion is invisible to a screen reader.
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
- [x] ~~Drop hub words above the 99th degree percentile~~ — **removed.** Degree measures
      connectedness, not genericness; the curated `GENERIC_HUBS` list does this instead
      (§7.3, Risk #19). `build-graph` still *reports* the top 40 as blocklist candidates.
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
- [x] `linkage export` — appends a batch; launch week hand-picked from the first batch, later batches shuffled with a fixed seed.
- [ ] **Corpus-level QC at export** (§7.7.1): word-reuse cap, no duplicate `(start, end)`, no repeated chains. **Fail loudly**, never ship quietly.
- [ ] Strip `meta` from the per-day files (§3.1).
- [ ] Run the determinism checklist (§7.8): generate twice, `diff` must be empty.
- [ ] **Verify:** `test_output_invariants.py`, `test_corpus_invariants.py`, and `test_subgraph_completeness.py` all pass **using fixtures only** — no dataset, no pickle.

### Phase 3 — Frontend Scaffold (TypeScript/React)

*Goal: the board renders from a real puzzle file. No interaction yet.*

- [x] `npm create vite@latest web -- --template react-ts`; add Tailwind.
- [x] `vite.config.ts` — set `base: '/Linkage/'` for GitHub Pages project sites.
- [x] `engine/types.ts` and `engine/ports.ts` (interfaces live in the domain tier).
- [x] ESLint `no-restricted-imports` on `src/engine/**` — no `react`, no DOM, no `fetch`.
- [x] `data/codec.ts` — the decoder; test it against the Python fixture **before** anything depends on it.
- [x] `HttpPuzzleRepository` + `validatePuzzle` runtime guard (all four checks, §8.4).
- [x] `LocalStorageProgressStore` with `try/catch` on every access.
- [x] Components: `Board`, `Slot`, `WordBank`, `Tile`, `AnchorWord`, plus `Header` with its four buttons (§8.5.1) — presentational only. Display casing via CSS, never stored (§3.1.1).
- [x] `App.tsx` states: loading / **network error with retry** / **no puzzle today** / ready (§8.7); `main.tsx` as composition root. `?puzzle=N` overrides the day, because the epoch is in the future and "today" resolves to nothing until launch.
- [x] **Verify:** today's puzzle renders with all 11 tiles; no game logic exists yet.

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
| 11 | **Win rate too low under a short life count + count-only feedback** | Medium | Kills the share loop — nobody posts a failure | **Instrument first:** we ship no analytics (§14), so measure by *manual playtest* — ~20 people play puzzles #1–#10 and report the numbers from their own `StatsPanel`. That sample easily separates a 30% win rate from a 70% one, which is all the resolution this decision needs. If under ~50%, tune puzzle difficulty (distractor temptingness, `MIN_EDGE_WEIGHT`, review strictness); an extra heart is the last resort. **This gate is also what settles `MAX_ATTEMPTS` itself** (§2.5.1) — dev builds run at 5. |
| 12 | **Golden test cannot run in CI** (needs the 1.2 GB dataset) | **Was certain** | The one test the game rests on never runs on a PR | **Resolved by design** — `verification-subgraph.json` (§7.10). CI runs on committed fixtures only. |
| 13 | **ConceptNet CC BY-SA 4.0 attribution / ShareAlike** | Certain | Licence violation on the derived puzzle data | Attribution in README, in-app About modal, and `puzzles/LICENSE.txt` (§12.2). Decide **before** Phase 1. |
| 14 | **Word repetition makes the year feel small** | High if unguarded | `gravity` in forty puzzles; players notice fast | `MAX_WORD_REUSE = 5` within any 120-puzzle rolling window, no duplicate `(start, end)` pairs, no repeated chains — enforced at export, `test_corpus_invariants.py` (§7.7.1). |
| 15 | **Acceptance rate lower than assumed; fewer than 365 approved** | Medium | Cannot fill a year | `generate --until-approved 365` tops up from a new seed offset, skipping already-decided content hashes (§7.7). Never assume one pass suffices. |
| 16 | **Not enough uniqueness-safe distractors for a puzzle** | Medium | Candidate discarded, yield drops further | Fall back to `BANK_SIZE = 10` (spec allows 10–12) before discarding the candidate (§7.9.4 Tier 4). |
| 17 | **Midnight passes with the tab open** | Certain for some players | Progress written under yesterday's ID; stale board | Recompute the puzzle number on `visibilitychange`/`focus`; prompt rather than yank the board (§8.7). |
| 18 | **Same-stem or overlapping words in one bank** | Medium | Looks sloppy; `moon` next to `moons` | Porter-stem comparison plus a substring check across the bank at selection time (§7.6). |
| 19 | ~~**Degree-percentile pruning is deleting good puzzle words**~~ | ~~Confirmed~~ **RESOLVED** | — | **Automatic pruning removed; the curated `GENERIC_HUBS` list does this job** (§7.3). All 75 words restored, `animal` through `bridge`. Degree is the wrong signal — it measures connectedness, not genericness. `build-graph` still reports the top 40 by degree as candidates for the curated list. |
| 20 | ~~**Generator enumerates paths exhaustively and never finishes**~~ | ~~High~~ **RESOLVED** | — | Per-pair path budget (`MAX_PATHS_PER_PAIR`) plus a pair budget, and one puzzle per endpoint pair. 900 candidates now come from 2,679 pairs in ~4 minutes. |
| 22 | **Scorer barely predicts reviewer taste** | **Confirmed, round 1** | The review queue is ordered little better than chance | 0.76 vs 0.75 between approved and rejected (§7.7.3). Rebuild `QualityScorer` from accumulated verdicts once several hundred exist — not from fresh guesses. Ordering a queue badly still yields a working queue, so this is a quality-of-life defect, not a blocker. |
| 23 | **Provable uniqueness ≠ perceived uniqueness** | **Confirmed, round 1** | Banks felt unfair even though every puzzle was provably unique | 95% of decoys were wired to one side of a slot. `DISTRACTOR_MIX` now spreads the draw across temptingness bands (§7.7.3). |
| 21 | ~~**Review burden is ~3× the plan's estimate**~~ | ~~Confirmed~~ **RESOLVED** | — | **The archive grows a month at a time** (§7.7.1). Launch needs ~40 approved candidates, not 2,500; `export` appends batches and diversity spans the whole archive so later months cannot reuse earlier vocabulary. Raising `MAX_WORD_REUSE` to 5 remains available if even monthly feels heavy. |

---

## 14. Explicitly Out of Scope

Listed so they are not accidentally built, and so the reasoning survives:

| Not building | Add when |
|---|---|
| User accounts / auth | Cross-device sync is actually requested. Bring Supabase then, not Workers. |
| Cross-device sync | Above. |
| Puzzle archive / play past dailies | Post-launch. Requires a date picker and a rethink of streaks. |
| Difficulty levels | We do not yet know what "hard" means empirically. Ship one difficulty, measure the distribution, then decide. |
| ~~Hint system~~ | **Moved in scope.** A hint button ships in the header; the mechanic behind it is undecided (§8.5.1). |
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
| A word appears in forty puzzles; the year feels small | `MAX_WORD_REUSE = 5` per 120-puzzle window, enforced at export | §7.7.1 |
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
| `MAX_ATTEMPTS` | **5 (provisional)** | 3 proved too harsh. Settled at the Phase 5 playtest gate from observed win rate (§2.5.1, Risk #11) — client-side only, does not block the generator. |
| `MIN_EDGE_WEIGHT` | 2.0 | Gate on the path's *weakest* edge. §7.9.4 Tier 1 may soften this to a rank. |
| `BFS_TOP_K` | 40 | Neighbours kept per frontier expansion. |
| `HUB_PERCENTILE` | `None` | **Automatic degree pruning is off** — the curated `GENERIC_HUBS` list does this job (§7.3, Risk #19). Set a float to re-enable; the machinery is kept and tested. |
| `HUB_REPORT_TOP_N` | 40 | Highest-degree words printed after a build, as curated-list candidates. |
| `ENFORCE_CHORDLESS` | `full` | `full` \| `minimal` \| `off` — see §7.9.4 Tier 2. `minimal` keeps the uniqueness proof intact. |
| `MAX_WORD_REUSE` | 5 | Times any word may appear **within a rolling window** (§7.7.1). |
| `WORD_REUSE_WINDOW` | 120 | Window length in puzzles, ~4 months. A word blocked today returns once it falls out the back. |
| `MIN_ENDPOINT_DEGREE` | 5 | A degree-1 endpoint has one possible neighbour and makes a forced rung. |
| `MAX_PATHS_PER_PAIR` | 8 | Per-pair search budget. Risk #20 -- 25 seeds once produced 33M paths. |
| `DISTRACTOR_POOL_SIZE` | 120 | Candidates each strategy proposes before ranking. |
| `DISTRACTOR_MIX` | (3, 2, 1) | Decoys drawn per cycle from the hard / medium / easy bands. Skimming the top made 95% of every bank a near-miss (§7.7.3). |
| `BANK_SIZE_MIN` | 10 | Fallback when too few uniqueness-safe distractors exist (Risk #16). |
| `HUB_DEGREE` (scoring) | 100 | Degree at which a step counts as fully generic (§7.7.2). |
| `BATCH_SIZE` | 30 | Puzzles added per `export` -- about a month. The archive grows incrementally (§7.7.1). |
| `TARGET_APPROVED` | 365 | The eventual archive depth, **not** a precondition for launching. |
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
linkage export                          # append ~a month of puzzles to the archive
linkage export --count 60               # a bigger batch
linkage export --replace                # rebuild the archive from scratch

pytest                                  # fixtures only — no dataset needed

# ---- Client (TypeScript) ----
cd web && npm ci

npm run dev                             # Vite dev server
npm test                                # vitest
npx playwright test                     # e2e smoke
npm run build                           # -> dist/, deployed by GitHub Actions
```

**Order of operations for a fresh archive:** `build-graph` → `diagnose` → *(climb the §7.9.4 ladder if yield is short)* → `generate` → `review` → `export` → `pytest` → commit.
