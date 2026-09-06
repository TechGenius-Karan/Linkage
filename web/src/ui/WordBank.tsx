/**
 * Presentation tier. The eleven tiles.
 *
 * Wrapped flex rather than a fixed grid on purpose: words run 3–12 characters
 * (planning.md 3.1.1), and a three-column grid at 360px clips anything past
 * about nine. Flex sizes to content and never truncates a word, at the cost of
 * a ragged last row.
 */

import { Tile, type TileState } from './Tile';

export interface WordBankProps {
  bank: string[];
  /** Words currently sitting in a slot — ghosted, not removed. */
  placed: readonly string[];
  selected: string | null;
  onTileClick?: ((word: string) => void) | undefined;
}

export function WordBank({ bank, placed, selected, onTileClick }: WordBankProps) {
  const placedSet = new Set(placed);

  return (
    <div className="flex flex-wrap justify-center gap-2" role="group" aria-label="Word bank">
      {bank.map((word) => {
        const state: TileState = placedSet.has(word)
          ? 'placed'
          : selected === word
            ? 'selected'
            : 'idle';
        return <Tile key={word} word={word} state={state} onClick={onTileClick} />;
      })}
    </div>
  );
}
