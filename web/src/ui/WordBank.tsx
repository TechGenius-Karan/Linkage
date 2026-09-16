/**
 * Presentation tier. The eleven tiles.
 *
 * Wrapped flex rather than a fixed grid on purpose: words run 3–12 characters
 * (planning.md 3.1.1), and a three-column grid at 360px clips anything past
 * about nine. Flex sizes to content and never truncates a word, at the cost of
 * a ragged last row.
 *
 * Also the one drop target a slot tile can be dragged onto to remove it —
 * `-mt-4 pt-4` (cancelling margin + padding) widens the droppable hit rect
 * upward without moving the visible tiles, so "near the bank" is genuinely
 * forgiving rather than a pixel-perfect target.
 */

import { useDroppable } from '@dnd-kit/core';
import { BANK_DROPPABLE_ID } from './dnd';
import { Tile, type TileState } from './Tile';

export interface WordBankProps {
  bank: string[];
  /** Words currently sitting in a slot — ghosted, not removed. */
  placed: readonly string[];
  selected: string | null;
  /** Words a hint has confirmed are in the answer (planning.md 2.5.3). */
  confirmed?: readonly string[] | undefined;
  /** The game is over — no tap, no drag. */
  disabled?: boolean | undefined;
  onTileClick?: ((word: string) => void) | undefined;
}

export function WordBank({ bank, placed, selected, confirmed, disabled, onTileClick }: WordBankProps) {
  const { setNodeRef, isOver } = useDroppable({ id: BANK_DROPPABLE_ID });
  const placedSet = new Set(placed);
  const confirmedSet = new Set(confirmed ?? []);

  return (
    <div
      ref={setNodeRef}
      className={`-mt-4 flex flex-wrap justify-center gap-2 rounded-2xl pt-4 ${
        isOver ? 'bank-drop-target' : ''
      }`}
      role="group"
      aria-label="Word bank"
    >
      {bank.map((word) => {
        const state: TileState = placedSet.has(word)
          ? 'placed'
          : selected === word
            ? 'selected'
            : 'idle';
        return (
          <Tile
            key={word}
            word={word}
            state={state}
            confirmed={confirmedSet.has(word)}
            disabled={disabled}
            onClick={onTileClick}
          />
        );
      })}
    </div>
  );
}
