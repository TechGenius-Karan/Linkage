/**
 * Presentation tier. One rung of the ladder.
 *
 * A real `<button>`, so keyboard and screen-reader support arrive for free
 * (planning.md 8.6). Every pointer gesture defined in 2.4 has a key here,
 * because a gesture with no keyboard path is a feature the accessibility
 * section forbids:
 *
 *   drag up/down/to bank  ->  ArrowUp / ArrowDown / Backspace / Delete
 *   double-tap            ->  Backspace / Delete
 *   (selection)            ->  Escape
 *
 * A filled slot is draggable to any other slot (reorder) or to the bank
 * (remove); every slot -- filled or empty -- is a drop target. The slot only
 * registers the gesture with `dnd-kit`; it cannot know where a drag lands,
 * only `<Game>` (the common parent of this and `<WordBank>`) sees both ends.
 */

import { useCallback, type KeyboardEvent } from 'react';
import { useDraggable, useDroppable } from '@dnd-kit/core';
import { slotDroppableId, type DragOrigin } from './dnd';

export type SlotState = 'empty' | 'filled' | 'reveal';

export interface SlotProps {
  index: number;
  word: string | null;
  state: SlotState;
  onClick?: ((index: number) => void) | undefined;
  onRemove?: ((index: number) => void) | undefined;
  /** Keyboard mirror of the drag-to-reorder gesture. */
  onNudge?: ((index: number, direction: -1 | 1) => void) | undefined;
  onEscape?: (() => void) | undefined;
  /** The game is over — no tap, no drag. */
  disabled?: boolean | undefined;
}

const STATE_CLASS: Record<SlotState, string> = {
  empty: 'slot-empty',
  filled: 'slot-filled',
  reveal: 'slot-reveal',
};

export function Slot({
  index,
  word,
  state,
  onClick,
  onRemove,
  onNudge,
  onEscape,
  disabled,
}: SlotProps) {
  const position = index + 1;
  const label =
    state === 'reveal'
      ? `Slot ${position}, answer was ${word}`
      : word !== null
        ? `Slot ${position}, ${word}`
        : `Slot ${position}, empty`;

  const droppable = useDroppable({ id: slotDroppableId(index) });
  const draggable = useDraggable({
    id: slotDroppableId(index),
    data: { origin: 'slot', index } satisfies DragOrigin,
    disabled: disabled === true || word === null,
  });
  const setRefs = useCallback(
    (node: HTMLButtonElement | null) => {
      draggable.setNodeRef(node);
      droppable.setNodeRef(node);
    },
    [draggable.setNodeRef, droppable.setNodeRef],
  );

  function handleKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    switch (event.key) {
      case 'ArrowUp':
      case 'ArrowDown': {
        if (onNudge === undefined || word === null) return;
        event.preventDefault(); // or the page scrolls under the player
        onNudge(index, event.key === 'ArrowUp' ? -1 : 1);
        return;
      }
      case 'Backspace':
      case 'Delete': {
        if (onRemove === undefined || word === null) return;
        event.preventDefault();
        onRemove(index);
        return;
      }
      case 'Escape':
        onEscape?.();
    }
  }

  return (
    <button
      ref={setRefs}
      type="button"
      data-slot={index}
      className={`slot ring-focus ${STATE_CLASS[state]} ${draggable.isDragging ? 'opacity-40' : ''} ${
        droppable.isOver ? 'slot-target' : ''
      }`}
      aria-label={label}
      onClick={onClick === undefined ? undefined : () => onClick(index)}
      onDoubleClick={onRemove === undefined ? undefined : () => onRemove(index)}
      onKeyDown={handleKeyDown}
      {...draggable.listeners}
      {...draggable.attributes}
    >
      {word ?? ' '}
    </button>
  );
}
