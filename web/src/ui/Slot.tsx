/**
 * Presentation tier. One rung of the ladder.
 *
 * A real `<button>`, so keyboard and screen-reader support arrive for free
 * (planning.md 8.6) and the key handling in Phase 4 has somewhere to live.
 */

export type SlotState = 'empty' | 'filled' | 'reveal';

export interface SlotProps {
  index: number;
  word: string | null;
  state: SlotState;
  onClick?: ((index: number) => void) | undefined;
  /** Double-tap / Backspace — returns the tile to the bank (planning.md 2.4). */
  onRemove?: ((index: number) => void) | undefined;
}

const STATE_CLASS: Record<SlotState, string> = {
  empty: 'slot-empty',
  filled: 'slot-filled',
  reveal: 'slot-reveal',
};

export function Slot({ index, word, state, onClick, onRemove }: SlotProps) {
  const position = index + 1;
  const label =
    state === 'reveal'
      ? `Slot ${position}, answer was ${word}`
      : word !== null
        ? `Slot ${position}, ${word}`
        : `Slot ${position}, empty`;

  return (
    <button
      type="button"
      className={`slot ring-focus ${STATE_CLASS[state]}`}
      aria-label={label}
      onClick={onClick === undefined ? undefined : () => onClick(index)}
      onDoubleClick={onRemove === undefined ? undefined : () => onRemove(index)}
    >
      {word ?? ' '}
    </button>
  );
}
