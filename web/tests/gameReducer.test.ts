/**
 * Every rule of the game (planning.md 8.2, 2.4, 2.5, 2.5.2, 2.5.3).
 *
 * Plain function calls — the reducer is curried over the puzzle, so none of
 * this needs React, a DOM, or a mock.
 */

import { describe, expect, it } from 'vitest';
import { elapsedMs, hintsRemaining, initialState, isBoardFull, makeGameReducer } from '../src/engine/gameReducer';
import { HINT_TIME_PENALTY_MS, type Action, type GameState, type Puzzle } from '../src/engine/types';

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

const NOW = 1_700_000_000_000;

const reduce = makeGameReducer(puzzle);
const run = (state: GameState, ...actions: Action[]) => actions.reduce(reduce, state);
const fresh = () => initialState(1, NOW);
const submit = (now = NOW): Action => ({ type: 'SUBMIT', now });

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

  it('costs time, not a life (planning.md 2.5.2)', () => {
    const s = run(fresh(), { type: 'TAKE_HINT' });
    expect(elapsedMs(s, NOW)).toBe(HINT_TIME_PENALTY_MS);
  });

  it('stacks the penalty across multiple hints', () => {
    const s = run(fresh(), { type: 'TAKE_HINT' }, { type: 'TAKE_HINT' });
    expect(elapsedMs(s, NOW)).toBe(2 * HINT_TIME_PENALTY_MS);
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

  it('does not name a word twice if taken again after running out', () => {
    const s = run(fresh(), { type: 'TAKE_HINT' }, { type: 'TAKE_HINT' }, { type: 'TAKE_HINT' });
    expect(elapsedMs(s, NOW)).toBe(2 * HINT_TIME_PENALTY_MS);
  });
});

describe('elapsedMs — the timer (planning.md 2.5.2)', () => {
  it('is zero the instant a puzzle starts', () => {
    expect(elapsedMs(fresh(), NOW)).toBe(0);
  });

  it('ticks with wall-clock time', () => {
    expect(elapsedMs(fresh(), NOW + 5_000)).toBe(5_000);
  });

  it('freezes while paused', () => {
    const s = run(fresh(), { type: 'PAUSE', now: NOW + 3_000 });
    expect(elapsedMs(s, NOW + 10_000)).toBe(3_000);
  });

  it('resumes counting from where it paused', () => {
    let s = run(fresh(), { type: 'PAUSE', now: NOW + 3_000 });
    s = run(s, { type: 'RESUME', now: NOW + 10_000 }); // paused for 7s
    expect(elapsedMs(s, NOW + 12_000)).toBe(5_000); // 3s before + 2s after
  });

  it('a second PAUSE while already paused does not stack', () => {
    let s = run(fresh(), { type: 'PAUSE', now: NOW + 3_000 });
    s = run(s, { type: 'PAUSE', now: NOW + 6_000 });
    s = run(s, { type: 'RESUME', now: NOW + 10_000 });
    expect(elapsedMs(s, NOW + 10_000)).toBe(3_000);
  });

  it('RESUME without a matching PAUSE is a no-op', () => {
    const s = run(fresh(), { type: 'RESUME', now: NOW + 5_000 });
    expect(elapsedMs(s, NOW + 5_000)).toBe(5_000);
  });

  it('freezes on the winning guess, regardless of when elapsedMs is later read', () => {
    const s = run(fresh(), ...fill(['ocean', 'blue', 'sky', 'birds']), submit(NOW + 40_000));
    expect(elapsedMs(s, NOW + 999_000)).toBe(40_000);
  });
});

describe('SUBMIT', () => {
  it('is ignored until all four slots are filled', () => {
    const s = run(fresh(), ...fill(['ocean', 'blue', 'sky']), submit());
    expect(s.attempts).toHaveLength(0);
  });

  it('reports how many slots are right, never which', () => {
    const s = run(fresh(), ...fill(['ocean', 'sea', 'sky', 'cloud']), submit());
    expect(s.attempts[0]?.correctCount).toBe(2);
    expect(Object.keys(s.attempts[0] ?? {})).toEqual(['tiles', 'correctCount']);
  });

  it('counts positionally, so the right words in the wrong order score low', () => {
    // All four solution words, none in place.
    const s = run(fresh(), ...fill(['birds', 'sky', 'blue', 'ocean']), submit());
    expect(s.attempts[0]?.correctCount).toBe(0);
  });

  it('wins on four correct', () => {
    const s = run(fresh(), ...fill(['ocean', 'blue', 'sky', 'birds']), submit());
    expect(s.status).toBe('won');
  });

  it('never ends the game on a wrong guess — guesses are free (planning.md 2.5.2)', () => {
    let s = fresh();
    for (let i = 0; i < 20; i++) {
      s = run(s, ...fill(['sea', 'cloud', 'shark', 'nest']), submit());
      expect(s.status).toBe('playing');
    }
  });

  it('accepts a win after many wrong guesses', () => {
    let s = fresh();
    for (let i = 0; i < 10; i++) s = run(s, ...fill(['sea', 'cloud', 'shark', 'nest']), submit());
    s = run(s, ...fill(['ocean', 'blue', 'sky', 'birds']), submit());
    expect(s.status).toBe('won');
  });

  it('clears the selection so a spent guess does not leave a tile held', () => {
    const s = run(fresh(), ...fill(['sea', 'cloud', 'shark', 'nest']), { type: 'SELECT_TILE', tileId: 'ocean' }, submit());
    expect(s.selectedTile).toBeNull();
  });
});

describe('terminal states are frozen', () => {
  const won = () => run(fresh(), ...fill(['ocean', 'blue', 'sky', 'birds']), submit(NOW + 1_000));

  it.each<Action>([
    { type: 'SELECT_TILE', tileId: 'sea' },
    { type: 'PLACE_TILE', slot: 0 },
    { type: 'MOVE_TILE', from: 0, to: 1 },
    { type: 'REMOVE_TILE', slot: 0 },
    { type: 'TAKE_HINT' },
    { type: 'SUBMIT', now: NOW + 5_000 },
    { type: 'PAUSE', now: NOW + 5_000 },
    { type: 'RESUME', now: NOW + 5_000 },
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
    const s = run(fresh(), ...fill(['ocean', 'blue', 'sky', 'birds']), submit());
    const json = JSON.stringify(s);
    expect(json).not.toContain('solution');
    expect(isBoardFull(s)).toBe(true);
  });
});
