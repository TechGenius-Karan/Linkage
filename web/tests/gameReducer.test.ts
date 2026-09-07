/**
 * Every rule of the game (planning.md 8.2, 2.4, 2.5, 2.5.3).
 *
 * Plain function calls — the reducer is curried over the puzzle, so none of
 * this needs React, a DOM, or a mock.
 */

import { describe, expect, it } from 'vitest';
import { hintsRemaining, initialState, isBoardFull, livesRemaining, makeGameReducer } from '../src/engine/gameReducer';
import { MAX_ATTEMPTS, type Action, type GameState, type Puzzle } from '../src/engine/types';

const puzzle: Puzzle = {
  schemaVersion: 1,
  id: 1,
  date: '2026-10-01',
  start: 'whale',
  end: 'wings',
  solution: ['ocean', 'blue', 'sky', 'birds'],
  hints: ['blue', 'birds'],
  bank: ['sea', 'ocean', 'cloud', 'sky', 'shark', 'blue', 'nest', 'wave', 'birds', 'color', 'feathers'],
};

const reduce = makeGameReducer(puzzle);
const run = (state: GameState, ...actions: Action[]) => actions.reduce(reduce, state);
const fresh = () => initialState(1);

/** Place `word` into `slot` the way a player would: select, then tap. */
const place = (word: string, slot: number): Action[] => [
  { type: 'SELECT_TILE', tileId: word },
  { type: 'PLACE_TILE', slot },
];

const fill = (words: string[]): Action[] => words.flatMap((w, i) => place(w, i));

describe('selection', () => {
  it('selects a bank tile', () => {
    expect(run(fresh(), { type: 'SELECT_TILE', tileId: 'ocean' }).selectedTile).toBe('ocean');
  });

  it('tapping the selected tile again deselects it', () => {
    const s = run(fresh(), { type: 'SELECT_TILE', tileId: 'ocean' }, { type: 'SELECT_TILE', tileId: 'ocean' });
    expect(s.selectedTile).toBeNull();
  });

  it('ignores a word that is not in the bank', () => {
    // The bank is the whole vocabulary of a puzzle; anything else is a bug or
    // a tampered payload.
    expect(run(fresh(), { type: 'SELECT_TILE', tileId: 'penguin' }).selectedTile).toBeNull();
  });

  it('ignores a tile already placed on the board', () => {
    const s = run(fresh(), ...place('ocean', 0), { type: 'SELECT_TILE', tileId: 'ocean' });
    expect(s.selectedTile).toBeNull();
  });
});

describe('placement', () => {
  it('places the held tile and clears the selection', () => {
    const s = run(fresh(), ...place('ocean', 0));
    expect(s.slots[0]).toBe('ocean');
    expect(s.selectedTile).toBeNull();
  });

  it('does nothing when no tile is held', () => {
    expect(run(fresh(), { type: 'PLACE_TILE', slot: 0 })).toEqual(fresh());
  });

  it('swaps rather than discarding when the slot is occupied', () => {
    // planning.md 2.4: PLACE_TILE onto a filled slot never silently drops a tile.
    const s = run(fresh(), ...place('ocean', 0), ...place('sky', 0));
    expect(s.slots[0]).toBe('sky');
    expect(s.slots).not.toContain('ocean');
  });

  it('moving a placed tile to another slot leaves one copy, not two', () => {
    const s = run(fresh(), ...place('ocean', 0), ...place('sky', 1));
    const moved = run(s, { type: 'MOVE_TILE', from: 0, to: 2 });
    expect(moved.slots.filter((w) => w === 'ocean')).toHaveLength(1);
  });

  it.each([-1, 4, 99, 1.5])('ignores an out-of-range slot (%s)', (slot) => {
    const s = run(fresh(), { type: 'SELECT_TILE', tileId: 'ocean' }, { type: 'PLACE_TILE', slot });
    expect(s.slots.every((x) => x === null)).toBe(true);
  });
});

describe('MOVE_TILE — the slide gesture (planning.md 2.4)', () => {
  it('exchanges two filled slots', () => {
    const s = run(fresh(), ...place('ocean', 0), ...place('sky', 1));
    const moved = run(s, { type: 'MOVE_TILE', from: 0, to: 1 });
    expect(moved.slots[0]).toBe('sky');
    expect(moved.slots[1]).toBe('ocean');
  });

  it('exchanging with an empty slot is a move', () => {
    const s = run(fresh(), ...place('ocean', 0));
    const moved = run(s, { type: 'MOVE_TILE', from: 0, to: 3 });
    expect(moved.slots[0]).toBeNull();
    expect(moved.slots[3]).toBe('ocean');
  });

  it('does not clear the selection', () => {
    // Reordering the ladder while holding a bank tile is legitimate.
    const s = run(fresh(), ...place('ocean', 0), { type: 'SELECT_TILE', tileId: 'sky' });
    expect(run(s, { type: 'MOVE_TILE', from: 0, to: 1 }).selectedTile).toBe('sky');
  });

  it('is a no-op when both slots are empty', () => {
    expect(run(fresh(), { type: 'MOVE_TILE', from: 0, to: 1 })).toEqual(fresh());
  });

  it('is a no-op onto itself', () => {
    const s = run(fresh(), ...place('ocean', 0));
    expect(run(s, { type: 'MOVE_TILE', from: 0, to: 0 })).toEqual(s);
  });

  it.each([
    [-1, 0],
    [0, 4],
    [0, 1.5],
  ])('ignores out-of-range indices (%s -> %s)', (from, to) => {
    // A gesture that misreports an index must not corrupt the board.
    const s = run(fresh(), ...place('ocean', 0));
    expect(run(s, { type: 'MOVE_TILE', from, to })).toEqual(s);
  });
});

describe('REMOVE_TILE — double-tap (planning.md 2.4)', () => {
  it('returns the tile to the bank', () => {
    const s = run(fresh(), ...place('ocean', 0), { type: 'REMOVE_TILE', slot: 0 });
    expect(s.slots[0]).toBeNull();
  });

  it('is a no-op on an empty slot', () => {
    expect(run(fresh(), { type: 'REMOVE_TILE', slot: 0 })).toEqual(fresh());
  });

  it('keeps the held tile', () => {
    const s = run(fresh(), ...place('ocean', 0), { type: 'SELECT_TILE', tileId: 'sky' });
    expect(run(s, { type: 'REMOVE_TILE', slot: 0 }).selectedTile).toBe('sky');
  });
});

describe('hints (planning.md 2.5.3)', () => {
  it('confirms words in the engine-ranked order', () => {
    const s = run(fresh(), { type: 'TAKE_HINT' });
    expect(s.hintsUsed).toEqual(['blue']);
    expect(run(s, { type: 'TAKE_HINT' }).hintsUsed).toEqual(['blue', 'birds']);
  });

  it('never places anything on the board', () => {
    // A hint gives membership, not position. If it placed a tile it would be
    // the reveal this mechanic exists instead of.
    const s = run(fresh(), { type: 'TAKE_HINT' }, { type: 'TAKE_HINT' });
    expect(s.slots.every((x) => x === null)).toBe(true);
  });

  it('never costs a life', () => {
    const s = run(fresh(), { type: 'TAKE_HINT' });
    expect(livesRemaining(s)).toBe(MAX_ATTEMPTS);
  });

  it('only ever names real answers', () => {
    const s = run(fresh(), { type: 'TAKE_HINT' }, { type: 'TAKE_HINT' });
    expect(s.hintsUsed.every((w) => puzzle.solution.includes(w))).toBe(true);
  });

  it('runs out rather than repeating', () => {
    const s = run(fresh(), { type: 'TAKE_HINT' }, { type: 'TAKE_HINT' }, { type: 'TAKE_HINT' });
    expect(s.hintsUsed).toEqual(['blue', 'birds']);
    expect(hintsRemaining(s, puzzle)).toBe(0);
  });

  it('never confirms the most obvious word', () => {
    // `sky` is the giveaway for this chain; handing it over buys nothing.
    const s = run(fresh(), { type: 'TAKE_HINT' }, { type: 'TAKE_HINT' });
    expect(s.hintsUsed).not.toContain('sky');
  });
});

describe('SUBMIT', () => {
  it('is ignored until all four slots are filled', () => {
    const s = run(fresh(), ...fill(['ocean', 'blue', 'sky']), { type: 'SUBMIT' });
    expect(s.attempts).toHaveLength(0);
  });

  it('reports how many slots are right, never which', () => {
    const s = run(fresh(), ...fill(['ocean', 'sea', 'sky', 'cloud']), { type: 'SUBMIT' });
    expect(s.attempts[0]?.correctCount).toBe(2);
    expect(Object.keys(s.attempts[0] ?? {})).toEqual(['tiles', 'correctCount']);
  });

  it('counts positionally, so the right words in the wrong order score low', () => {
    // All four solution words, none in place.
    const s = run(fresh(), ...fill(['birds', 'sky', 'blue', 'ocean']), { type: 'SUBMIT' });
    expect(s.attempts[0]?.correctCount).toBe(0);
  });

  it('wins on four correct', () => {
    const s = run(fresh(), ...fill(['ocean', 'blue', 'sky', 'birds']), { type: 'SUBMIT' });
    expect(s.status).toBe('won');
  });

  it('loses only after every life is spent', () => {
    let s = fresh();
    s = run(s, ...fill(['sea', 'cloud', 'shark', 'nest']));
    for (let i = 1; i < MAX_ATTEMPTS; i++) {
      s = run(s, { type: 'SUBMIT' });
      expect(s.status).toBe('playing');
      expect(livesRemaining(s)).toBe(MAX_ATTEMPTS - i);
    }
    s = run(s, { type: 'SUBMIT' });
    expect(s.status).toBe('lost');
    expect(livesRemaining(s)).toBe(0);
  });

  it('accepts a win on the final life', () => {
    let s = run(fresh(), ...fill(['sea', 'cloud', 'shark', 'nest']));
    for (let i = 1; i < MAX_ATTEMPTS; i++) s = run(s, { type: 'SUBMIT' });
    s = run(s, ...fill(['ocean', 'blue', 'sky', 'birds']), { type: 'SUBMIT' });
    expect(s.status).toBe('won');
  });

  it('clears the selection so a spent guess does not leave a tile held', () => {
    const s = run(fresh(), ...fill(['sea', 'cloud', 'shark', 'nest']), { type: 'SELECT_TILE', tileId: 'ocean' }, { type: 'SUBMIT' });
    expect(s.selectedTile).toBeNull();
  });
});

describe('livesRemaining', () => {
  it('does not charge a life for the winning guess', () => {
    // A life is lost by being wrong. Charging for the win renders a first-try
    // solve with a drained heart, which reads as a penalty on the one screen
    // people screenshot.
    const s = run(fresh(), ...fill(['ocean', 'blue', 'sky', 'birds']), { type: 'SUBMIT' });
    expect(s.status).toBe('won');
    expect(livesRemaining(s)).toBe(MAX_ATTEMPTS);
  });

  it('charges only the failed guesses on a later win', () => {
    let s = run(fresh(), ...fill(['sea', 'cloud', 'shark', 'nest']));
    s = run(s, { type: 'SUBMIT' }, { type: 'SUBMIT' });          // two wrong
    s = run(s, ...fill(['ocean', 'blue', 'sky', 'birds']), { type: 'SUBMIT' });
    expect(s.status).toBe('won');
    expect(livesRemaining(s)).toBe(MAX_ATTEMPTS - 2);
  });

  it('reaches zero on a loss', () => {
    let s = run(fresh(), ...fill(['sea', 'cloud', 'shark', 'nest']));
    for (let i = 0; i < MAX_ATTEMPTS; i++) s = run(s, { type: 'SUBMIT' });
    expect(s.status).toBe('lost');
    expect(livesRemaining(s)).toBe(0);
  });
});

describe('terminal states are frozen', () => {
  const won = () => run(fresh(), ...fill(['ocean', 'blue', 'sky', 'birds']), { type: 'SUBMIT' });

  it.each<Action>([
    { type: 'SELECT_TILE', tileId: 'sea' },
    { type: 'PLACE_TILE', slot: 0 },
    { type: 'MOVE_TILE', from: 0, to: 1 },
    { type: 'REMOVE_TILE', slot: 0 },
    { type: 'TAKE_HINT' },
    { type: 'SUBMIT' },
  ])('ignores %o after the game ends', (action) => {
    const end = won();
    expect(reduce(end, action)).toEqual(end);
  });

  it('still accepts RESTORE, which is how a finished board survives a refresh', () => {
    const end = won();
    const restored = reduce(end, { type: 'RESTORE', state: fresh() });
    expect(restored.status).toBe('playing');
  });
});

describe('the solution never enters state', () => {
  it('is absent from a serialised game', () => {
    // GameState goes into localStorage and is visible in React DevTools. The
    // reducer is curried over the puzzle precisely so the answer stays out.
    const s = run(fresh(), ...fill(['ocean', 'blue', 'sky', 'birds']), { type: 'SUBMIT' });
    const json = JSON.stringify(s);
    expect(json).not.toContain('solution');
    expect(isBoardFull(s)).toBe(true);
  });
});
