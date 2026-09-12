# The Admin Tool

*A local tool for reviewing, refining and scheduling puzzles. Not part of the
game, and never deployed.*

This document is the whole design record for the admin. It was §16 of
`planning.md` until the admin grew past the point where it belonged inside the
product spec — the same move `docs/engine.md` made for §7, and for the same
reason: only the admin needs it, and `planning.md` is read by anyone touching
the game.

`planning.md` keeps a short §16 stub naming the two facts that constrain the
*rest* of the project — the tool is local-only and must never ship — and points
here for everything else.

**Status.** All of it is built. §§1–8 shipped as Phase 6a/6b/6c (PRs #9, #10);
§§9–14 shipped as 6d/6e/6f.

---

## Part I — What exists

### 1. Why it is local, and why that is not a compromise

The obvious model is the one a sibling project uses: an admin page served from
the public site, gated by a shared access code, backed by a database. Two facts
make that actively wrong here rather than merely expensive.

**Generation needs the graph, and the graph is 1.2 GB on one laptop.** A
deployed admin could review a queue but never top it up, which is half a tool.
Reviewing and generating belong on the same machine because generating has
nowhere else to run.

**Puzzles ship as files committed to git.** A verdict stored in a remote
database would need a sync step before it reached a player. A local tool writes
`engine/decisions.json` directly, and `git commit` *is* the publish step — which
is already the workflow (`planning.md` §12).

So the admin binds to `127.0.0.1` and has **no authentication at all**. That is
not a shortcut. The safest gate is nothing exposed; an access code exists in the
sibling project because its admin ships to a public URL, and ours must not.

> **Reviewing from a phone:** `--host` exposes it on the local network, the same
> way the dev server already is. Anyone on that network can then open it. There
> is nothing behind it but puzzle answers, and it is a home network — but it is
> a deliberate choice each time, not a default.

### 2. The state machine

```
  candidate ──approve──► approved (undated) ──schedule──► scheduled (date + id)
      │                       ▲     │                            │
      └── reject ─────────────┘     └── unapprove                └── unschedule
          (reason, badLink)
```

**Approve records taste. Scheduling is a separate act.** Round 1's reviewer was
explicit about this — an approval must not imply a shipping date — and
`docs/engine.md` §7.7.3 lists the coupling as an open defect. The undated
pool is where it gets fixed: `approved` carries `date: null` until somebody
chooses one.

`decisions.json` is keyed by content hash, so re-running `generate` never
discards a judgement already made (`docs/engine.md` §7.7). The record:

```jsonc
{ "66898f743924cd8f": {
    "verdict":   "accept",        // or "reject"
    "reason":    null,            // free text, required on reject
    "badLink":   null,            // WHICH rung failed, 0..4
    "bankEdits": [],              // swaps made in review, for auditing
    "date":      null,            // scheduling, deliberately separate
    "decidedAt": "2026-09-10" } }
```

`read_decisions` stays tolerant of the old `hash -> verdict` shape, so a
`decisions.json` written by the terminal TUI still loads.

**`badLink` is the point of the whole exercise.** Round 1's single most useful
finding was that *one* bad link ruined otherwise-good chains, and
`docs/engine.md` §7.7.3 records that letting a reviewer say which link failed
is worth more than any heuristic guessed from here. A free-text reason cannot
be aggregated; a rung index can.

> **What `badLink` has already found, 45 verdicts in.** Of the 14 rejections
> that named a rung:
>
> ```
>   link 0  start->w1   ###            3
>   link 1  w1->w2      #######        7
>   link 2  w2->w3      ###            3
>   link 3  w3->w4                     0
>   link 4  w4->end     #              1
> ```
>
> **13 of 14 fall in the opening half, and half of those on link 1 alone.**
> Nothing in the generator looks for this: `MIN_EDGE_WEIGHT` gates a path on its
> weakest edge wherever that edge sits, and `step_balance` scores the *spread*
> of weights, not their position. Neither can express "the second rung is where
> these break".
>
> A guess at why: the first two rungs are where a chain commits to a direction.
> `article → reading → fun` was rejected because *"reading isn't necessarily fun
> for everyone"*; `animals → zoo → elephant` because it *"takes it right back to
> an example of an animal"*. Both are second-rung failures of direction, not of
> edge weight — exactly the kind of thing a weight cannot see.
>
> Too few verdicts to retune on. But it is already a sharper signal than
> anything the scorer has (`docs/engine.md` §7.7.2: 0.76 vs 0.75 between
> approved and rejected), it took 45 verdicts rather than several hundred to
> surface, and no free-text reason could have produced it. It is the whole
> argument for §9 optimising for *volume*.

### 3. Shape

```
engine/src/linkage_engine/
  admin/server.py        TIER 1  stdlib http.server on 127.0.0.1
  admin/handlers.py      TIER 1  parse -> domain call -> JSON
  domain/decisions.py    TIER 2  the state machine. Pure, no I/O, fully tested.
  domain/distractors.py  TIER 2  swap_decoy + safe_swaps — the engine's veto

web/src/admin/           lazy-loaded; dropped from the production build
  AdminApp      tab shell
  ReviewCard    one candidate, with its links clickable
  BankEditor    swap a decoy, under the engine's veto
  PoolPage      the undated pool and the run of slots
  adminClient.ts
```

`http.server` from the standard library, not Flask or FastAPI. One reviewer, on
one machine, over localhost — a framework would be a dependency earning nothing.

Nine endpoints: `queue`, `approve`, `reject`, `undo`, `swap`, `swaps`, `pool`,
`schedule`, `unschedule`.

Two more than the seven originally planned, and both earned their place. `undo`
because a reviewer is one keystroke from a wrong verdict and hesitates over
every click without a way back. `swaps` because a swap the reviewer cannot aim
is not a feature — it offers the replacements the engine has already proved, so
the menu never leads somewhere refused (§5).

> **No health dashboard.** An earlier draft had another endpoint reporting
> archive coverage and word-reuse pressure. Cut: the number that actually
> matters is whether *this* puzzle on *this* date breaks a rule, and that
> belongs beside the date picker (§7), not on a separate screen nobody opens.

**`linkage review` — the terminal TUI — is kept, not replaced.** It works, it
needs no browser, and it is the fallback when the server will not start.

### 4. The graph loads lazily

Only the swap routes need the 1.2 GB dataset's derived graph (a 3.4 MB pickle).
It loads on the first request that needs it, not at startup, so a missing or
stale graph costs exactly the one feature that cannot work without it —
approving, rejecting and scheduling all keep working.

### 5. Refine means swapping a word, and the engine gets a veto

A sibling project's Refine hands the reviewer's notes to a model that rewrites
the puzzle. Nothing like that applies here: this generator is deterministic
graph search, not a language model, and there is nothing to negotiate with.

What transfers is the **shape** of the interaction, and one hard-won rule from
that project's own source: *refine and reject must be different buttons.* They
had merged them once, and asking for a fix could silently discard the puzzle.

So: **swap one bank word for another, and the engine re-runs the uniqueness
proof before accepting it.** If the swap would make a second solution possible,
it is refused with the reason — the reviewer cannot break the one property the
whole game rests on, even by hand. A refused swap leaves the puzzle untouched
and in the queue.

Measured on the real graph: **373 of 1000 trial swaps are refused**, e.g.
`whale → wings: cloud → eggs` would have admitted a second valid answer. The
veto is not decorative.

This aims directly at round 1's other finding: the banks were uniformly too
hard, because 95% of every bank was a decoy wired to one side of a solution
slot (`docs/engine.md` §7.7.3). `DISTRACTOR_MIX` addresses that in generation;
swapping addresses the ones that still slip through.

#### 5.1 Where an edit is stored, and why not on the candidate

The obvious place to put a swapped bank is `candidates.json`, next to the bank
it replaces. That is wrong, and the reason is worth writing down because it is
not visible from the code that reads it.

`Candidate.content_hash()` covers **the bank as a set**. It has to: the hash is
what lets `generate` run again without discarding a judgement a person already
made, and a re-run reshuffles the bank. So editing the bank in place changes the
hash, and the decision holding that edit is instantly orphaned — the tool would
lose the reviewer's work as a side effect of recording it.

So the edit lives on the **decision**, as an ordered list, and is replayed over
the generated puzzle on every read. The candidate file is never rewritten. This
also gets auditability for nothing: the edit is a record of what a person
changed, not a silent overwrite of what the generator produced.

**This is the single most load-bearing structural decision in the admin**, and
§11 extends it rather than replacing it.

#### 5.2 An edit is a preview until the puzzle is approved

An edit could reasonably be its own write — edit now, decide later. It is not,
because that would need a fourth state (*edited, undecided*) in a machine whose
smallness is the point.

Instead the edit endpoint proves the change and returns the result **without
writing anything**, the UI holds the pending edits, and `approve` carries them.
An edit is therefore an argument about a puzzle you are about to accept, which
is what it actually is — nobody hand-tunes a puzzle they are going to reject.
`approve` re-proves rather than trusting what the client sends: the check costs
60 ms, and this is the one property the whole game rests on.

### 6. The admin must never ship

There is no server-side gate, so a deployed admin is an open door onto the
answer key. It is excluded from the production build by `import.meta.env.DEV`,
and **`web/scripts/assert-no-admin.mjs` fails the build if any admin string
reaches `dist/`**.

The check matters more than the flag, and it is a build step rather than a test
on purpose: a test can be skipped, and this is the one that must not be. A
tree-shake that silently stops working produces a deploy that looks completely
normal and gives no sign at all.

Verified in both directions on every change — clean on a real build, exit 1 when
a forbidden string is planted in `dist/`.

### 7. Corpus QC belongs beside the date picker

`docs/engine.md` §7.7.1 checks word reuse, duplicate endpoint pairs and repeated chains at export,
and **fails loudly**. That is correct and, on its own, useless: by the time
export runs, thirty decisions have already been made, and "the archive is bad"
is not an instruction anybody can act on.

The same checks run when a date is chosen, against the archive plus everything
already scheduled — so the reviewer sees *"`river` would appear 6 times in 120
puzzles"* while they can still pick a different day. Export keeps its hard gate;
this is the warning that makes the gate rarely fire.

It earned its place on first contact with real data: scheduling `WHALE → WINGS`
immediately reported *"whale / wings already ship together on 2026-10-01"* and
*"this exact chain already ships on 2026-10-01"*. At export that is a hard
failure discovered after thirty decisions.

### 8. Scheduling picks a slot, not a date

`date == EPOCH_DATE + (id - 1)` days is the archive's one hard invariant, and
the golden test asserts it. A free-form date picker quietly contradicts it: a
reviewer choosing the 5th while the 3rd is empty has asked for a gap, and a gap
renumbers every puzzle after it or breaks the invariant outright.

So the pool offers a **contiguous run of slots** and scheduling claims one.
Export then walks that run in order: a pinned day takes its puzzle, every other
day draws from auto-selection, and the run **stops at the first day neither can
fill**. A pin sitting past that point is reported rather than shipped, because
moving it forward to close the gap would put a puzzle on a date the reviewer did
not choose, and dropping it silently is indistinguishable from having shipped it.

Auto-assignment is therefore still doing almost all the work. The difference is
that it now fills *around* human choices instead of overriding them.

---

## Part II — Round 2: what review at volume actually needs

*Everything below is proposed, not built.*

### 9. The problem this round solves

The tool works. It has been used for exactly 33 verdicts, and the queue holds
**867 undecided candidates**. Every complaint below is about the gap between
those two numbers.

The first version optimised for *care* — one puzzle, centred, nothing else on
screen, because a wall of cards invites skimming and skimming is the failure
mode a human gate exists to prevent. That was right for round 1. It is wrong
now, for a reason worth stating precisely:

**A verdict is cheap; a context switch is not.** Judging a chain takes a couple
of seconds. Waiting for a refetch, re-finding your place, and re-orienting to a
new puzzle takes longer than the judgement did. At 33 verdicts that overhead is
invisible. At 867 it *is* the task.

So this round trades a little of the one-at-a-time discipline for throughput,
and pays for it by making each card easier to judge rather than easier to skip.

### 10. The interface changes

#### 10.1 Direction: a reading desk

The reviewer's whole job is reading word chains and deciding whether they read
well *to a person*. So the surface is editorial — the type of a well-set
reference book, not the chrome of a dashboard.

**Serif for everything textual, mono for data about text, and no UI sans at
all.** A third family would only blur the one distinction that carries meaning
here: words versus counts. Source Serif 4 for the words, JetBrains Mono for
counts, dates and slot chips.

The palette is "book brown + page amber" over warm paper, with a real dark
ramp rather than an inversion.

> **Revised after first use.** The original plan said the admin would share the
> game's eight tokens exactly — one ramp, no second system to keep in sync. In
> practice that produced a screen with a *single* ink colour, so every line
> shouted equally and the eye had nowhere to land; in dark mode it read as
> undifferentiated white text. The fix is not more colours but more **levels**:
> three inks (`ink` / `ink-soft` / `ink-faint`) and two surfaces, so hierarchy
> comes from contrast rather than from size alone.
>
> These live in `web/src/admin/admin.css`, imported by `AdminApp` — which is
> lazy, so the tokens and the webfonts travel with the admin chunk and never
> reach a player. Moving them out of the shared stylesheet made the *game's*
> CSS smaller (15.3 → 11.6 kB). `assert-no-admin` greps `dist/` for the font
> URL and an admin class name, so a leak fails the build.

#### 10.1.1 What was removed, and why

Round 2 shipped a screen that was correct and unreadable. Three things went:

- **The edge weight on every rung**, as a number and a bar. The reviewer judges
  whether two words *read* as related; the weight is ConceptNet's confidence,
  which the generator needs and a reader does not. Five per card across five
  cards is twenty-five numbers to not look at. It survives in the connector's
  tooltip.
- **The content hash and quality score** on each card. Neither is something a
  person reads a chain against.
- **The `START → END` card heading**, which restated the first and last word of
  the chain printed directly beneath it.

What did *not* go is the click target between two words. `badLink` is the most
valuable thing this tool collects, so the connector stays — now a rule you
press rather than a bar with a number on it.

#### 10.2 The ladder turns sideways

The current card stacks its six words vertically, which costs ~280 px of height
for six short words and makes five cards impossible.

```
  now                          proposed
  ────                         ────────
  PAINTING                     PAINTING ─2.0─ canvas ─2.0─ covering ─2.0─ hood ─2.0─ neighborhood ─4.0─ DRIVEWAY
    ↓ 2.0 RelatedTo                      ▁▁▁          ▁▁▁           ▁▁▁         ▁▁▁               ████
  canvas
    ↓ 2.0 UsedFor              one line, and the weakest rung is visible
  covering                     without reading a single number
    ↓ 2.0 IsA
  hood
    ↓ 2.0 IsA
  neighborhood
    ↓ 4.0 AtLocation
  DRIVEWAY
```

The bar under each link encodes its weight. This is not decoration:
`docs/engine.md` §7.4 gates a path on its **weakest** edge because one weak
link is what makes a chain feel unfair, and `badLink` exists because round 1
proved reviewers reject on exactly that. Making the weakest rung the visually
loudest thing on the card puts the eye where the decision is. Relations
(`IsA`, `AtLocation`) move to a tooltip — they matter when adjudicating a
doubtful link, not while scanning.

#### 10.3 Five at a time

Five cards in one scrolling column. Deciding one removes it and the next
candidate appears at the bottom; the other four keep their positions.

This needs **no client-side bookkeeping**, which is why five is affordable at
all. The queue is sorted deterministically by `(-quality, hash)`, so "the first
five pending" after a verdict is, by construction, the four survivors in their
original order plus one new arrival. The client refetches and renders the first
five. There is no list to reconcile and no way for the two to drift.

> **Why not infinite scroll over all 867?** Because the refetch-after-verdict
> trick stops working: every verdict would reshuffle an arbitrarily long list,
> and holding scroll position through that needs exactly the bookkeeping the
> five-card window avoids. Five is the largest window that stays trivially
> correct.

#### 10.4 Progress, and the undo that already exists

A thin rule under the header: `33 of 900 decided`. Not a dashboard (§3 rejected
one) — a single number answering "am I getting anywhere", which is the question
that decides whether a reviewer keeps going.

The existing undo banner stays, and moves inline with the card it undoes rather
than sitting at the top of the page.

### 11. Manual editing

The ask: a button on a queue card that lets the reviewer rewrite **any** word —
bank decoys, the four answer words, and both endpoints — then approve.

**The reviewer decides whether the puzzle still holds.** That is the governing
rule of this section and it settles every question the rest of it raises. A
human gate exists here precisely because ConceptNet is wrong a lot: round 1's
rejections were overwhelmingly *"ConceptNet says these two relate and they
plainly do not."* A tool that accepts the reviewer's verdict on the generator's
output and then refuses their correction — on the grounds that the same dataset
they just overruled does not contain the edge — has the authority backwards.

So a manual edit is accepted on the reviewer's say-so. The rest of this section
is what the machinery has to do to make that stick, and the one narrow question
that is still the machine's to answer.

#### 11.1 How an edit is stored

Manual edits extend the §5.1 mechanism rather than inventing a second one.
`BankEdit` generalises to:

```python
@dataclass(frozen=True, slots=True)
class WordEdit:
    field: Literal["start", "end", "solution", "bank"]
    index: int | None      # position in solution; None elsewhere
    removed: str
    added: str
```

Replayed in order over the generated puzzle, keyed by the **original** content
hash so the decision is never orphaned. Existing `bankEdits` entries load as
`field="bank"`, so no migration. The candidate file is still never rewritten.

Words are normalised on entry exactly as the engine normalises them (lowercase,
`[a-z]` only, 3–12 chars, no multiword), because a word that cannot survive
normalisation cannot ship.

#### 11.2 A hand-asserted link has to be recorded, or CI throws the puzzle out

This is not an argument against the edit. It is what the edit requires.

The golden test (`test_output_invariants.py`) re-solves every shipped puzzle on
every CI run — but against `verification-subgraph.json`, not the 1.2 GB dataset,
which CI does not have. That fixture is built as the induced subgraph **over
ConceptNet**. So a rung the reviewer asserted, which ConceptNet has no edge for,
simply would not be in the file. The shipped puzzle would re-solve to **zero**
solutions and CI would fail — not because the puzzle is bad, but because the
evidence for it was never exported.

So the assertion is recorded on the decision and exported with it:

```jsonc
"manualEdges": [["roof", "shingle", 2.0]]
```

The reviewer's judgement becomes part of the shipped evidence, which is what it
already is in substance. Three consequences, all small:

- The editor **says plainly** when a rung is not attested by ConceptNet. Not to
  block it — to tell the reviewer they are the source for that link, which is
  worth knowing while deciding.
- `linkage export` reports the count: *"3 of 30 puzzles ship a hand-authored
  link."* A number nobody sees is a number nobody checks.
- Manual edges need a weight, because `hints.obviousness()` ranks answer words
  by the strength of the links either side. Default `MIN_EDGE_WEIGHT` (2.0),
  overridable.

#### 11.3 The one question that stays the machine's

Two questions look similar and are not:

| Question | Who can answer it |
|---|---|
| Does `roof → shingle` read as a real link? | **The reviewer.** No machine can; that is the whole point of the gate. |
| Do these eleven words admit a *second* valid ordering? | **The machine.** It is a fact about 7,920 arrangements that nobody can see by eye. |

The first is taste and knowledge, and the reviewer wins it outright. The second
is arithmetic, and getting it wrong means a player arranges the board correctly
and is told they are wrong — which is not a difficulty problem, it is a broken
promise (`planning.md` §2.3).

So **uniqueness stays an absolute veto, and chordlessness with it.** Worth
noting how little this costs in practice: adding an edge can only ever *create*
solutions, never remove them, so the proof simply re-runs over ConceptNet plus
whatever the reviewer asserted, and refuses only in the specific case where the
reviewer's own edit has handed the player a second right answer. That is a
refusal they would want.

Everything else — is the chain plausible, is it too hard, is it interesting, is
this word better than that one — is the reviewer's, and the tool does not get an
opinion.

#### 11.4 The editor itself

Deliberately plain, as asked. A pencil on the card turns its words into inputs:
six chain slots and the bank chips. On blur the whole puzzle is re-checked and
the card shows either its new state, a note naming any rung now resting on the
reviewer's word rather than ConceptNet's, or — only for uniqueness — a refusal.
Approve stays disabled while a refusal is outstanding.

### 12. Three screens, and a lane for second thoughts

The two tabs become three.

```
  REVIEW                    SCHEDULE                  UPCOMING
  ──────                    ────────                  ────────
  5 candidates              approved, undated         already dated
  + sent-back lane          next 7 open days          in date order

  approve / reject          schedule → date           return to pool
  edit / mark bad link      send back to review
```

#### 12.1 The sent-back lane

An approved puzzle can be returned to review — "I said yes and I want another
look" — from the Schedule screen. It must not vanish into the 867; it is a
puzzle *you already chose*, and finding it again would be impossible.

So the review screen gets a second section above the queue:

```
  Sent back for another look (1)
  ┌──────────────────────────────────────────────────┐
  │ WHALE ─ ocean ─ blue ─ sky ─ birds ─ WINGS       │
  └──────────────────────────────────────────────────┘

  Queue — 867 pending
  ┌──────────────────────────────────────────────────┐  1 of 5
  ...
```

Five plus one sent-back is six cards on screen, which is the requested
behaviour. Sent-back cards are **additional to** the five, never part of them.

This needs a fourth verdict, `"revisit"`, and that is a real widening of the §2
machine rather than a flag:

```
  candidate ──approve──► approved ──schedule──► scheduled
      ▲                    │  ▲                     │
      └──── revisit ───────┘  └─── unschedule ──────┘
```

A `revisit` decision is excluded from the pool and from export, appears only in
its own lane, and is overwritten by the next approve or reject. It is stored
rather than deleted so the reviewer's history is not silently rewritten —
`decisions.json` is durable human judgement, not a build artifact.

**It carries no note.** `reject` demands a reason because rejections are the
data that will eventually rebuild `QualityScorer`; "I want another look" is a
state change and teaches the generator nothing. The only feedback that reaches
the system comes from approve and reject in the review queue, and adding a
second place to type would dilute the one that matters.

#### 12.2 The next seven open days

The Schedule screen currently reveals dates only after clicking into a puzzle,
and then shows all thirty. Both are wrong: thirty is a wall, and hiding them
means you cannot see what you are scheduling *into*.

A persistent strip at the top of the screen, showing the **next seven
unscheduled days** with what already sits around them:

```
  Next open days          ( archive ends 2026-10-01 )
  ┌─────┬─────┬─────┬─────┬─────┬─────┬─────┐
  │10-02│10-03│10-05│10-06│10-07│10-09│10-10│      10-04, 10-08 taken
  └─────┴─────┴─────┴─────┴─────┴─────┴─────┘
```

Seven, not thirty, because a week is the unit a person actually plans in, and
the run is thirty days long — a reviewer who has filled seven can see the next
seven. Skipped dates are named rather than hidden, so a gap is visible before
export reports it (§8).

#### 12.3 The Upcoming screen

A read-mostly list of what is dated, in date order, with the date, the chain,
and whether it carries hand edits. One action: **return to pool** — which is
`unschedule`, already built and already distinct from unapproving (the reviewer
still likes the puzzle; they want a different day).

It needs **no new endpoint**: `pool` already returns `scheduled`. A separate
screen rather than a section because "what is shipping over the next month" is a
different question from "what should I schedule next", asked at a different
time.

### 13. What this adds up to

Endpoints: nine become ten. `revisit` is new; `swap` generalises to `edit`
(taking `WordEdit`s rather than only bank swaps) and keeps its veto; `swaps`
generalises from bank slots to any slot.

| Endpoint | Change |
|---|---|
| `queue` | returns the first **5** pending plus a `returned` list |
| `edit` | was `swap`; now any word, still writes nothing, still vetoes |
| `swaps` | suggestions for any slot, not only bank slots |
| `approve` | carries `WordEdit`s and any `manualEdges` |
| `revisit` | **new** — approved → back to review |
| `pool` | gains `openDays` (the next seven) |
| `reject` `undo` `schedule` `unschedule` | unchanged |

Domain: `WordEdit` replaces `BankEdit` with a loader for the old shape;
`"revisit"` joins the `Verdict` union; a `validate_puzzle` function puts the
uniqueness and chordlessness proofs (§11.3) in one place, so the editor,
`approve` and export all ask the machine the same question — and ask it only
about the things that are the machine's to answer.

Web: `AdminApp` gains a third tab; `ReviewCard` turns sideways; `BankEditor`
becomes `PuzzleEditor`; `UpcomingPage` is new.

Export gains the manual-edge union into the verification subgraph (§11.2) and a
line in its report counting hand-authored links.

### 14. Build order

Independently mergeable, each useful alone, riskiest thing last.

**6d — The interface.** *(done)* Sideways ladder, five cards, progress rule,
and the editorial surface of 10.1. No API change at all beyond a `limit`.
Ships the throughput win on its own.

**6e — Three screens and the sent-back lane.** *(done)* `revisit` verdict,
`UpcomingPage`, the seven-day strip. Pure state-machine work, no graph.

**6f — Manual editing.** *(done)* `WordEdit`, `validate_puzzle`, the editor UI, and
manual edges carried through to the exported subgraph. Last because it is the
only part that can put a puzzle in front of a player that no generator ever
checked.

**Verification, throughout.** The golden test is the backstop and must stay
green; `assert-no-admin` must stay green and keep failing on a planted string;
every new veto gets a test from both sides, and 6f gets one that proves a
hand-edited puzzle still re-solves to exactly one answer from the shipped
subgraph alone.

---

## Settled in review

1. **Manual edits — the reviewer's judgement governs (§11).** ConceptNet is
   overruled by the person who is already overruling it every day. The machine
   keeps exactly one veto, uniqueness, because it is arithmetic over 7,920
   arrangements rather than a matter of taste (§11.3).
2. **No keyboard layer.** Dropped from the plan entirely.
3. **`revisit` records no note (§12.1).** The only feedback that reaches the
   system is approve and reject from the review queue. "I want another look" is
   a state change, not data.
