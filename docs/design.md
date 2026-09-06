# Linkage — Visual Design

> The companion to §8 of [`../planning.md`](../planning.md). §8 specifies the
> *architecture* of the client — reducer, ports, component tree — and says
> nothing about how any of it looks. This document is that half.
>
> **Status:** proposed · nothing implemented yet

---

## 1. The Brief

> **Simple and basic, nothing fancy — but it should still look good, and comforting.**

"Comforting" is a real constraint, not a mood word, and it rules things out:

| Not this | Because |
|---|---|
| Pure `#FFF` on pure `#000` | Clinical. High-contrast neutrals read as *tool*, not *pastime*. |
| Saturated primaries, gradients, glass | Every one of them competes for attention with the words. |
| Red for a spent life | Red is alarm. Losing a heart should land as a small cost, not a warning. |
| Bouncy / spring motion | Playful motion reads as urgent. §1.3's north star is a *pause*. |
| Timers, counters ticking up | §2.5.2 already settled this. Nothing on screen should hurry the player. |

### The one rule

**The words are the content. Everything else is furniture.**

A player spends their session reading eleven words and turning them over. Any
pixel that is not a word is competing with the thing the game is actually
about. This is why the palette is nearly monochrome, why there is exactly one
piece of ornament, and why the layout is a single centred column.

It also means the plainness is *not* a compromise for lack of time. It is the
design.

---

## 2. Palette

Two hues total — one calm accent, one warm one — over a warm neutral ramp. A
warm ground is doing most of the work here: `#FAF7F2` is barely off white, and
it is the whole difference between "app" and "paper".

```css
:root {
  --ground:     #FAF7F2;   /* page — warm paper, never #FFF          */
  --surface:    #FFFFFF;   /* tiles, cards — lifts off the ground     */
  --rule:       #E3DCD2;   /* the ladder line, borders, spent hearts  */
  --ink:        #1F1D1A;   /* words — warm near-black, never #000     */
  --ink-muted:  #6B6560;   /* labels, counts, secondary text          */
  --accent:     #2F6F63;   /* selection, focus, the Check button      */
  --accent-sub: #E7EFEC;   /* selected-tile fill                      */
  --heart:      #C96F4A;   /* lives remaining — clay, not red         */
}

:root:not([data-theme="light"]) { }        /* see §2.1 */
```

### 2.1 Dark

Not an inversion — a second warm ramp. Inverting a warm light theme gives a
blue-grey dark theme, which loses the only property the palette was chosen for.

```css
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --ground:     #1A1815;
    --surface:    #24211D;
    --rule:       #35312B;
    --ink:        #EFE9E1;
    --ink-muted:  #9C948A;
    --accent:     #6FB5A5;
    --accent-sub: #23332F;
    --heart:      #E29068;
  }
}
```

Every pair above clears 4.5:1 for text on its own ground (§8.6). `--rule` is
decorative and deliberately does not — it is never the sole carrier of meaning.

### 2.2 Feedback colours

There are none. `correctCount` is stated in words — *"3 of 4 correct"* — and
that is the entire feedback channel. Count-only feedback is colourblind-safe
for free (§2.5) and adding a colour to it would be inventing a signal the
game does not have.

The share grid is the one exception, and only because it must survive being
pasted as plain text: 🟨 ⬜ 🟩 are emoji, not our palette.

---

## 3. Type

System stacks. A word game is 100% text, so a webfont is the single most
tempting dependency here and the least necessary one — the plan's whole ethos
is a ~50 KB app that loads instantly (§14).

```css
--font-word: 'Iowan Old Style', 'Palatino Linotype', Palatino, Georgia, serif;
--font-ui:   system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
```

**A serif for the words, a sans for the chrome.** The split is doing real work:
it marks what is *content* and what is *interface* without needing a box, a
rule, or a colour to say so. It also gives the words a little warmth that a
system sans cannot.

| Element | Family | Size | Weight | Notes |
|---|---|---:|---:|---|
| Anchor words (START / END) | word | 28px | 600 | `text-transform: uppercase`, `letter-spacing: .02em` |
| Tile / slot word | word | 17px | 500 | Lowercase in data, displayed as-is (§3.1.1) |
| Feedback line | ui | 15px | 500 | *"3 of 4 correct"* |
| Labels, counts, header | ui | 13px | 500 | `--ink-muted` |
| Modal body | ui | 15px | 400 | line-height 1.55 |

> **Upgrade path if the system serif proves ugly on Android** (Georgia is not
> universally present): subset one variable serif to `[a-z]` + uppercase, which
> lands around 15 KB woff2. Do this only after seeing it on a real device —
> `ponytail:` system stack, swap in a subset webfont if Android renders poorly.

---

## 4. Space & Size

4px base unit. Everything is a multiple.

| Token | Value | Used for |
|---|---:|---|
| `--gap-tile` | 8px | Between bank tiles, between slots |
| `--gap-block` | 24px | Between board / bank / submit bar |
| `--pad-tile` | 12px 14px | Inside a tile |
| `--radius-tile` | 10px | Tiles, slots |
| `--radius-modal` | 16px | Share, stats, how-to-play |

- **Minimum touch target 44×44px** (§8.6). At 17px type plus 12px vertical
  padding a tile is ~44px tall naturally; do not shrink the padding to fit more
  tiles per row.
- **Board column: `max-width: 360px`, centred.** Wider does not help — the
  ladder is vertical, and a long line length makes the eleven bank words harder
  to scan, not easier.
- **Elevation is one shadow, used once:** `0 1px 2px rgb(31 29 26 / .06)` on
  tiles. Slots are inset (a `--rule` border, no shadow) so the difference
  between "a thing you pick up" and "a place you put it" is legible before any
  colour is involved.

---

## 5. The Board

```
                     APPLE              anchor · serif · uppercase
                       │
                   ┌───┴───┐
                   │       │            slot 1 · empty
                   └───┬───┘
                   ┌───┴───┐
                   │ moon  │            slot 2 · filled
                   └───┬───┘
                   ┌───┴───┐
                   │       │            slot 3 · empty
                   └───┬───┘
                   ┌───┴───┐
                   │       │            slot 4 · empty
                       │
                     OCEAN              anchor
```

**The vertical rule is the only ornament in the entire game.** A 2px line in
`--rule`, running from beneath the start anchor to above the end anchor,
passing behind the slots. It is what makes the board read as a *ladder* rather
than a list, and it costs one pseudo-element.

Do not add a second ornament. If the board looks bare, the fix is spacing.

### 5.1 States

**Tile** — `idle · selected · placed`

| State | Treatment |
|---|---|
| `idle` | `--surface` fill, `--ink` text, the one shadow |
| `selected` | `--accent-sub` fill, 2px `--accent` border, no shadow — it has been *picked up* |
| `placed` | Stays in the bank at 35% opacity, non-interactive |

> **`placed` tiles are ghosted, not removed.** Pulling a tile out of the bank
> reflows every remaining tile, so the board rearranges itself under the
> player's thumb four times per attempt. Holding the grid still is worth the
> slightly emptier look.

**Slot** — `empty · filled · focus`

| State | Treatment |
|---|---|
| `empty` | `--ground` fill, 1px dashed `--rule` border |
| `filled` | `--surface` fill, 1px solid `--rule` border, serif word |
| `dragging` | Lifted: shadow to `0 4px 10px rgb(31 29 26 / .10)`, `z-index` above its siblings, follows the pointer on the Y axis only |
| `focus` | 2px `--accent` outline, offset 2px — the same ring used everywhere |

> **Slot fills are opaque, including when empty.** The ladder rule is drawn
> behind them, so a transparent empty slot lets the line run straight through
> the middle of the box and it reads as a strikethrough rather than a spine.
> Opaque fills clip it to the gaps, which is the intended look: a dotted
> connector, not a continuous bar.

**Slide feedback.** The slot being dragged lifts; the slot it would exchange
with dims to 60% opacity. Nothing reflows and nothing animates into place until
the pointer is released — a ladder that rearranges itself mid-drag makes the
target impossible to aim at. On release, both slots settle over 160ms.

`touch-action: manipulation` on every slot and tile, or a double-tap zooms the
page instead of clearing the slot (§2.4).

**Lives** — `♥` in `--heart`, spent ones `♥` in `--rule`. Outline glyphs and
greyed-out fills both read as "empty"; a filled-but-drained heart reads as
*spent*, which is the feeling §2.5.1 is after. Always accompanied by
`aria-label="4 of 5 lives remaining"`.

---

## 6. Motion

| Transition | Duration | Easing |
|---|---:|---|
| Tile select / deselect | 120ms | `ease-out` |
| Tile into slot | 160ms | `ease-out` |
| Modal in | 220ms | `ease-out` |
| Solution reveal on loss | 200ms per rung, staggered 80ms | `ease-out` |

Nothing springs, nothing bounces, nothing scales past 1.0. The loss reveal is
the one place a stagger is justified — the chain is read top to bottom, and
showing it all at once wastes the only moment the player gets to see *why*.

```css
@media (prefers-reduced-motion: reduce) {
  * { animation-duration: .01ms !important; transition-duration: .01ms !important; }
}
```

---

## 7. Layout Order

Mobile-first, single column, no horizontal scroll at 320px. Ordered by how
often a thing is touched — most-tapped lowest, where the thumb is.

```
  Header            Linkage  #142        ? ⚙ ▤ ✦    (rarely touched)
  Board             anchors + 4 slots
  Lives + feedback  ♥♥♥♥♥   "3 of 4 correct"
  Attempt history   past rows, collapsed to counts
  Word bank         11 tiles                         (tapped most)
  Check             full-width button                (tapped once per attempt)
```

**The four header buttons** — hint, statistics, how to play, settings — sit in
a right-aligned row opposite the wordmark. They are 40×40px icon buttons with
a 44px hit area, `--ink-muted` at rest and `--ink` on hover, no fill and no
border. Four affordances in the header is already at the limit of what stays
calm; a fifth needs a menu instead.

They are the only icons in the product, which is why they must be genuinely
plain — a single stroke weight, no filled shapes, nothing that reads as a
brand mark competing with the wordmark beside them.

The board must never require a scroll on a phone (§ Phase 5). If it does, the
first thing to cut is `--gap-block`, then attempt history collapses to a single
line.

---

## 8. Not Doing

| Not building | Add when |
|---|---|
| A component library | Eight components. Tailwind covers it. |
| An icon set | Three glyphs — heart, share, question mark. Inline SVG. |
| Webfonts | §3. Only if Android renders the system serif badly. |
| An animation library | §6 is six CSS transitions. |
| A theme switcher UI | `prefers-color-scheme` follows the OS. A manual toggle is a preference to persist and a state to test, for a choice the player already made once. |
| Illustration, mascot, empty-state art | Competes with the words. |
| A loading skeleton | The payload is ~1 KB. It is never on screen long enough to skeleton. |
