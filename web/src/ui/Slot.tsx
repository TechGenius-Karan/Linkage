/**
 * Presentation tier. One rung of the ladder.
 *
 * A real `<button>`, so keyboard and screen-reader support arrive for free
 * (planning.md 8.6). Every pointer gesture defined in 2.4 has a key here,
 * because a gesture with no keyboard path is a feature the accessibility
 * section forbids:
 *
 *   slide up/down   ->  ArrowUp / ArrowDown
 *   double-tap      ->  Backspace / Delete
 *   (selection)     ->  Escape
 *
 * The slot reports intent; `<Board>` owns the geometry and decides what a
 * gesture meant, because a slot cannot know which slot it was dragged onto.
 */

import type { PointerEvent as ReactPointerEvent, KeyboardEvent } from 'react';

export type SlotState = 'empty' | 'filled' | 'reveal';

export interface SlotProps {
  index: number;
  word: string | null;
  state: SlotState;
  /** Pixels this slot is currently displaced by, while being dragged. */
  dragOffset?: number | undefined;
  /** True when a drag would land here — dimmed so the target is visible. */
  isDropTarget?: boolean | undefined;
  onClick?: ((index: number) => void) | undefined;
  onRemove?: ((index: number) => void) | undefined;
  /** Keyboard mirror of the slide gesture. */
  onNudge?: ((index: number, direction: -1 | 1) => void) | undefined;
  onDragStart?: ((index: number, event: ReactPointerEvent<HTMLButtonElement>) => void) | undefined;
  onEscape?: (() => void) | undefined;
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
  dragOffset,
  isDropTarget,
  onClick,
  onRemove,
  onNudge,
  onDragStart,
  onEscape,
}: SlotProps) {
  const position = index + 1;
  const label =
    state === 'reveal'
      ? `Slot ${position}, answer was ${word}`
      : word !== null
        ? `Slot ${position}, ${word}`
        : `Slot ${position}, empty`;

  const dragging = dragOffset !== undefined && dragOffset !== 0;

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
      type="button"
      data-slot={index}
      className={`slot ring-focus ${STATE_CLASS[state]} ${dragging ? 'slot-dragging' : ''} ${
        isDropTarget === true ? 'slot-target' : ''
      }`}
      style={dragOffset === undefined ? undefined : { transform: `translateY(${dragOffset}px)` }}
      aria-label={label}
      onClick={onClick === undefined ? undefined : () => onClick(index)}
      onDoubleClick={onRemove === undefined ? undefined : () => onRemove(index)}
      onKeyDown={handleKeyDown}
      onPointerDown={
        onDragStart === undefined || word === null ? undefined : (e) => onDragStart(index, e)
      }
    >
      {word ?? ' '}
    </button>
  );
}
