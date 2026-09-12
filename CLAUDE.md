# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Linkage is a daily word puzzle: connect a start word to an end word with a
ladder of exactly four intermediate words, chosen from an 11-word bank salted
with red-herring distractors. Two independent programs, sharing one file
format as their only interface:

- **`engine/`** — Python. Offline puzzle generation from a ConceptNet graph.
  Run locally, roughly monthly. Never runs in CI (needs a 1.2 GB dataset).
- **`web/`** — TypeScript/React/Vite. The static client that plays the
  puzzles. Deployed to GitHub Pages.

They meet only at `web/public/puzzles/*.json`. Neither half imports the
other. `planning.md` is the full design doc (~1500 lines); `docs/engine.md`
holds the deep-dive on the generation algorithm (moved out because only the
engine needs it); `docs/design.md` covers product/game design. Read
`planning.md`'s table of contents before a big change — the section you need
is almost certainly already written down, with the reasoning and the
alternatives that were rejected.

## Commands

### Engine (Python, from `engine/`)

```bash
python -m pip install -e engine
python -m nltk.downloader wordnet omw-1.4

linkage build-graph              # downloads ConceptNet (~1.2GB, 20-40 min), builds the graph
linkage inspect <word>            # spot-check a word's neighbours
linkage diagnose                  # yield funnel + go/no-go before generating
linkage generate --count 900      # emit ranked, uniquely-solvable candidates
linkage review                    # terminal accept/reject TUI
linkage admin                     # serve the browser review tool on 127.0.0.1:8787
linkage export                    # append a batch to web/public/puzzles/
linkage import-verdicts           # fold engine/reviews/*.json into decisions.json
```

Run tests with `pytest` from `engine/` (config lives in `pyproject.toml`:
`testpaths = ["tests"]`, `pythonpath = ["src"]`). Single test:
`pytest tests/test_pathfinder.py::test_name`.

### Web (TypeScript, from `web/`)

```bash
npm run dev          # vite dev server
npm run build         # tsc -b && vite build && assert-no-admin check
npm run test          # vitest run
npm run test:watch
npm run lint          # eslint src tests
npm run typecheck     # tsc -b --noEmit
```

Single test file: `npx vitest run tests/gameReducer.test.ts`.

`npm run build` fails the build if any admin code leaked into `dist/`
(`scripts/assert-no-admin.mjs` greps the built output for admin-only
strings) — see "The admin tool" below before touching anything under
`src/admin/`.

## Architecture

### Three-tier, applied twice

Both halves use the same Presentation / Domain / Data layering, so there's
one mental model for the whole repo. **Dependency rule: dependencies point
inward.** The domain tier imports nothing from presentation or data.

**Engine (Python):**
- Presentation — `cli.py` (Typer commands), `review.py` (TUI)
- Domain — `domain/*.py`: pure functions, no I/O, no network
  (`pathfinder`, `distractors`, `validator`, `scoring`, `generator`, `corpus`, `decisions`, `hubs`)
- Data — `data/*.py`: everything touching the outside world
  (`conceptnet`, `vocabulary`, `graph_store`, `codec`, `exporters`)

**Web (TypeScript), enforced by an ESLint `no-restricted-imports` rule:**
- `ui/` — presentational components, props in / events out. May import `engine/`, `data/`, React, Tailwind.
- `engine/` — `gameReducer`, `dailyIndex`, `stats`, `types`, `ports`. **Must never import** `react`, `fetch`, `localStorage`, `window`, `document`.
- `data/` — `httpPuzzleRepository`, `localStorageProgressStore`, `codec`. May only import `engine/` types.

The interfaces `data/` implements (`PuzzleRepository`, `ProgressStore`) are
declared in `engine/ports.ts` — the logic tier owns the contract, the data
tier conforms to it (Dependency Inversion). `main.tsx` is the **only** file
that instantiates concrete implementations (the composition root); every
test builds the app against stub implementations instead, with no mocking
framework needed.

### The data contract (`web/public/puzzles/*.json`)

The single interface between the two programs — changing its shape is a
breaking change requiring a `schemaVersion` bump on both sides. Full shape
in `planning.md` §3. Key points:

- One file per day (`2026-10-01.json`, ~1 KB), not one bundle with every
  answer — `manifest.json` gives count/epoch so the client can compute
  today's puzzle number without a 404 round-trip.
- Each file is XOR-obfuscated (repeating key = the date string) then
  base64'd — **obfuscation, not encryption**, just enough to stop casual
  DevTools snooping. The codec must be byte-identical between
  `engine/data/codec.py` (encoder) and `web/src/data/codec.ts` (decoder);
  `engine/fixtures/codec-fixture.json` is a Python-generated payload the TS
  suite decodes to prove it, regenerate with `linkage emit-codec-fixture`.
- Words are normalised once, identically on both sides: lowercase, ASCII
  `[a-z]` only, 3–12 chars, no multiword (`_`-containing ConceptNet URIs are
  dropped at parse time). Display uppercasing is CSS-only, never stored.
- `date` must equal `epoch + (id - 1)` days — the golden test in
  `test_output_invariants.py` asserts this.

### Why puzzles ship as committed files, not a generated-in-CI artifact

CI must never touch the 1.2 GB ConceptNet dump. `web/public/puzzles/**` is
committed, generated locally by `linkage export`, and reviewed like any
other change. The "golden test" that re-solves every shipped puzzle and
proves a unique solution runs against `engine/fixtures/verification-subgraph.json`
— the induced subgraph over just the words each puzzle actually uses (a few
hundred KB), not the full graph. That file must contain *every* edge among
those words, not just the solution path, or the uniqueness proof is
vacuous. It's committed but deliberately excluded from `web/public/` (it's
effectively a plaintext answer key).

Fixing one bad puzzle after launch: edit that single day's file, run
`linkage export --verify-only` to refresh the manifest and subgraph, commit.
Never regenerate the whole archive — the seed-shuffled ordering would
reassign every date and puzzle number that's already been shared.

### Pathfinding, uniqueness, and why they're strict

Puzzles need exactly 5 edges (`S → w1 → w2 → w3 → w4 → E`) that are
**chordless** (no shortcut edges among the 6 nodes) — this isn't just a
quality filter, it's what makes the four-word solution provably the *only*
valid ordering, reducing "is this puzzle unique" to "do the distractors
avoid creating an alternate." Distractors are added one at a time to the
bank, keeping only ones that don't break uniqueness (built correct by
construction, not generated-then-filtered). `docs/engine.md` §7.4–7.9 has
the full reasoning, including a large yield-measurement exercise that closed
out what was originally the project's top technical risk — don't re-derive
that analysis, it's already been measured.

### The admin tool (`engine/admin/`, `web/src/admin/`)

A local-only review UI for accepting/rejecting/scheduling candidates — not
part of the game, never deployed. Binds to `127.0.0.1` with **no
authentication by design** (the safest gate is nothing exposed; `--host`
exists to expose it to your LAN for phone review, and that's a deliberate
per-run choice, not a default). Backend is stdlib `http.server`
(`admin/server.py`, `admin/handlers.py`) — no Flask/FastAPI for one
reviewer on one machine. The state machine (`domain/decisions.py`) is:
`candidate → approve/reject → approved (undated) → schedule → scheduled`.
Approving records taste; scheduling a date is a deliberately separate act.

Because there's no server-side auth, a deployed copy of this UI would be an
open door onto the answer key — see `web/scripts/assert-no-admin.mjs`,
which runs on every `npm run build` and fails it if any admin-only string
(`ReviewCard`, `adminClient`, `/api/admin/`, etc.) shows up in `dist/`. If
you touch `src/admin/` or how it's excluded from the production bundle
(`main.tsx` gates it behind `import.meta.env.DEV`), verify that check still
passes — a silently-broken tree-shake would ship completely normal-looking
output.

## Conventions worth knowing before you change something

- **Determinism matters.** Same inputs must produce byte-identical output
  years from now, so the archive is rebuildable. This means: a single
  seeded `random.Random`, never module-level `random`; sort before any
  iteration order affects output (`sorted(bank)`, `(-weight, word)` on
  neighbours); dependency versions in `engine/pyproject.toml` are pinned
  exactly, not range-pinned (`wordfreq` in particular bundles frequency
  data that changes between releases and would silently change every
  puzzle).
- **All tunable constants live in `engine/config.py`**, not scattered
  through source — and only the ones that actually change the built graph
  are hashed into its fingerprint (`GRAPH_AFFECTING_FIELDS`), so changing a
  puzzle-shape constant like `bank_size` doesn't trigger a bogus "graph is
  stale" warning.
- **Hub words are pruned by a curated list (`domain/wordlists.GENERIC_HUBS`),
  not a degree threshold.** A degree-percentile cutoff was tried and measured
  to actively remove good puzzle words (`bird`, `animal`, `bridge`) because
  degree measures connectedness, not genericness. Don't reintroduce
  automatic degree pruning without rereading `docs/engine.md` §7.3.
- **Reject vs. reason.** Any UI/CLI surface that lets a reviewer reject a
  candidate must collect a reason (and ideally which link in the chain
  failed) — this was the single most useful signal from the first real
  review round and drives future generation tuning.
- Decisions (`engine/decisions.json`) are keyed by content hash and are
  never regenerated — treat this file as durable human judgement, not a
  build artifact, and never overwrite an existing entry when writing
  migration/import code.
