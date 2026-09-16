/**
 * Presentation tier. One bank word.
 *
 * `tileId` is the word itself — the bank is a set of unique words, proven by
 * `validatePuzzle`, so no separate identity is needed (planning.md 3.1.1).
 *
 * Draggable to any slot in `<Board>`, in addition to the tap-to-select it has
 * always had — `useDraggable` just registers the gesture; `<Game>` (the
 * common parent of this and `<Board>`) decides what a drop meant.
 */

import { useDraggable } from '@dnd-kit/core';
import { bankDraggableId, type DragOrigin } from './dnd';

export type TileState = 'idle' | 'selected' | 'placed';

export interface TileProps {
  word: string;
  state: TileState;
  /**
   * A hint has confirmed this word is in the answer (planning.md 2.5.3).
   * Independent of `state`: a confirmed word can also be idle, selected or
   * placed, and stays marked for the rest of the game.
   */
  confirmed?: boolean | undefined;
  /** The game is over — no tap, no drag. */
  disabled?: boolean | undefined;
  onClick?: ((word: string) => void) | undefined;
}

const STATE_CLASS: Record<TileState, string> = {
  idle: '',
  selected: 'tile-selected',
  placed: 'tile-placed',
};

export function Tile({ word, state, confirmed, disabled, onClick }: TileProps) {
  const dragDisabled = disabled === true || state === 'placed';
  const draggable = useDraggable({
    id: bankDraggableId(word),
    data: { origin: 'bank', word } satisfies DragOrigin,
    disabled: dragDisabled,
  });

  return (
    <button
      ref={draggable.setNodeRef}
      type="button"
      className={`tile ring-focus ${STATE_CLASS[state]} ${confirmed === true ? 'tile-confirmed' : ''} ${
        draggable.isDragging ? 'opacity-40' : ''
      }`}
      // A placed tile stays in the bank at 35% rather than being removed:
      // pulling it out reflows the grid under the player's thumb four times an
      // attempt (docs/design.md 5.1). Game-over is handled by `onClick` and
      // `useDraggable`'s own `disabled` above, not this attribute — a native
      // `disabled` button picks up the browser's UA dimming, which would
      // visibly darken every untouched bank tile the instant the game ends.
      disabled={state === 'placed'}
      {...draggable.listeners}
      {...draggable.attributes}
      // After the spread: `useDraggable`'s own `attributes` sets
      // `aria-pressed` to mean "currently being dragged," which would
      // otherwise silently win over the tap-selection meaning this button
      // has always used it for.
      aria-pressed={state === 'selected'}
      // The mark is a border, and a border alone is not a signal a screen
      // reader can read (planning.md 8.6).
      aria-label={confirmed === true ? `${word}, confirmed in the answer` : undefined}
      onClick={onClick === undefined ? undefined : () => onClick(word)}
    >
      {word}
    </button>
  );
}
