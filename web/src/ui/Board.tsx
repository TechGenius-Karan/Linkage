/**
 * Presentation tier. The ladder (planning.md 2.2, 2.4).
 *
 * Pointer-drag (reorder within the board, drag to the bank, drag from the
 * bank) is `dnd-kit`, wired up in `<Game>` — the common parent of this and
 * `<WordBank>`, and the only component that can see both ends of a drag that
 * crosses between them. Each `<Slot>` registers itself as a draggable and a
 * drop target; this component stays a thin list, same as before. The keyboard
 * mirror of drag-to-reorder (arrow keys) is the one thing still wired
 * point-to-point here, since it never leaves the column.
 */

import { Fragment } from 'react';
import { AnchorWord } from './AnchorWord';
import { Slot, type SlotState } from './Slot';

/** Connects one rung to the next. The only ornament in the game (docs/design.md 5). */
function Connector() {
  return (
    <svg
      width="14"
      height="9"
      viewBox="0 0 12 8"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="text-ink-muted"
      aria-hidden="true"
    >
      <path d="M1 1l5 5 5-5" />
    </svg>
  );
}

export interface BoardProps {
  start: string;
  end: string;
  slots: (string | null)[];
  revealed?: string[] | undefined;
  onSlotClick?: ((index: number) => void) | undefined;
  onSlotRemove?: ((index: number) => void) | undefined;
  /** Arrow-key reorder only — pointer-drag reorder goes through `dnd-kit`. */
  onNudge?: ((from: number, to: number) => void) | undefined;
  onEscape?: (() => void) | undefined;
  /** The game is over — no tap, no drag. */
  disabled?: boolean | undefined;
}

export function Board({
  start,
  end,
  slots,
  revealed,
  onSlotClick,
  onSlotRemove,
  onNudge,
  onEscape,
  disabled,
}: BoardProps) {
  return (
    <div className="relative flex flex-col items-center gap-1.5">
      <AnchorWord word={start} position="start" />
      <Connector />

      {slots.map((word, i) => {
        // On a loss the chain replaces whatever the player had, rather than
        // filling their gaps. Their board is full of wrong tiles at that point,
        // so revealing only the empty slots revealed nothing -- and the message
        // beside it says "here is the chain".
        const reveal = revealed?.[i];
        const state: SlotState =
          reveal !== undefined ? 'reveal' : word !== null ? 'filled' : 'empty';
        return (
          <Fragment key={i}>
            <Slot
              index={i}
              word={reveal ?? word}
              state={state}
              onClick={onSlotClick}
              onRemove={onSlotRemove}
              onNudge={
                onNudge === undefined
                  ? undefined
                  : (index, direction) => {
                      const to = index + direction;
                      if (to >= 0 && to < slots.length) onNudge(index, to);
                    }
              }
              onEscape={onEscape}
              disabled={disabled}
            />
            <Connector />
          </Fragment>
        );
      })}

      <AnchorWord word={end} position="end" />
    </div>
  );
}
