/**
 * Presentation tier. One bank word.
 *
 * `tileId` is the word itself — the bank is a set of unique words, proven by
 * `validatePuzzle`, so no separate identity is needed (planning.md 3.1.1).
 */

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
  onClick?: ((word: string) => void) | undefined;
}

const STATE_CLASS: Record<TileState, string> = {
  idle: '',
  selected: 'tile-selected',
  placed: 'tile-placed',
};

export function Tile({ word, state, confirmed, onClick }: TileProps) {
  return (
    <button
      type="button"
      className={`tile ring-focus ${STATE_CLASS[state]} ${confirmed === true ? 'tile-confirmed' : ''}`}
      // A placed tile stays in the bank at 35% rather than being removed:
      // pulling it out reflows the grid under the player's thumb four times an
      // attempt (docs/design.md 5.1).
      disabled={state === 'placed'}
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
