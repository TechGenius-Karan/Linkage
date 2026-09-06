/**
 * Presentation tier. The ladder (planning.md 2.2, 8.5).
 *
 * `<Board>` owns the row geometry because a `<Slot>` cannot know which slot it
 * was dragged onto — only their common parent can. In Phase 4 the pointer
 * handlers live here and dispatch `MOVE_TILE { from, to }`; the slots stay pure
 * functions of props either way.
 *
 * The ladder rule is the only ornament in the game. It is drawn behind the
 * column and clipped by the slots' opaque fills, so it shows in the gaps as a
 * connector rather than running through the middle of every box.
 */

import { AnchorWord } from './AnchorWord';
import { Slot, type SlotState } from './Slot';

export interface BoardProps {
  start: string;
  end: string;
  /** Length CHAIN_LENGTH. `null` is an empty slot. */
  slots: (string | null)[];
  /** Shown in place of an empty slot when the game is lost. */
  revealed?: string[] | undefined;
  onSlotClick?: ((index: number) => void) | undefined;
  onSlotRemove?: ((index: number) => void) | undefined;
}

export function Board({
  start,
  end,
  slots,
  revealed,
  onSlotClick,
  onSlotRemove,
}: BoardProps) {
  return (
    <div className="relative flex flex-col items-center gap-2.5">
      {/* The rule. Inset so it starts below the start word and ends above the
          end word, and behind everything else (z-0 against the slots' z-1). */}
      <div
        className="pointer-events-none absolute left-1/2 top-9 bottom-9 z-0 -ml-px w-0.5 bg-rule"
        aria-hidden="true"
      />

      <AnchorWord word={start} position="start" />

      {slots.map((word, i) => {
        const reveal = word === null ? revealed?.[i] : undefined;
        const state: SlotState =
          reveal !== undefined ? 'reveal' : word !== null ? 'filled' : 'empty';
        return (
          <Slot
            key={i}
            index={i}
            word={word ?? reveal ?? null}
            state={state}
            onClick={onSlotClick}
            onRemove={onSlotRemove}
          />
        );
      })}

      <AnchorWord word={end} position="end" />
    </div>
  );
}
