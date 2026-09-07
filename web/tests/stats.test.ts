/**
 * Streaks and the distribution (planning.md 2.8).
 *
 * The streak rule is the one people notice being wrong, because a broken
 * streak is the thing a daily-game player is most attached to.
 */

import { describe, expect, it } from 'vitest';
import { emptyStats, recordResult, winPercent } from '../src/engine/stats';
import { MAX_ATTEMPTS, type GameState, type Stats } from '../src/engine/types';

const game = (
  puzzleId: number,
  status: 'won' | 'lost' | 'playing',
  attempts = 1,
): GameState => ({
  puzzleId,
  slots: ['a', 'b', 'c', 'd'],
  attempts: Array.from({ length: attempts }, () => ({ tiles: [], correctCount: 0 })),
  status,
  selectedTile: null,
  hintsUsed: [],
});

const play = (stats: Stats, ...games: GameState[]) => games.reduce(recordResult, stats);

describe('recordResult', () => {
  it('ignores a game still in progress', () => {
    expect(recordResult(emptyStats(), game(1, 'playing'))).toEqual(emptyStats());
  });

  it('counts a win', () => {
    const s = recordResult(emptyStats(), game(1, 'won', 3));
    expect(s.gamesPlayed).toBe(1);
    expect(s.wins).toBe(1);
    expect(s.currentStreak).toBe(1);
    expect(s.maxStreak).toBe(1);
    expect(s.distribution[2]).toBe(1); // 3 attempts -> bucket index 2
  });

  it('counts a loss without touching the histogram', () => {
    const s = recordResult(emptyStats(), game(1, 'lost', MAX_ATTEMPTS));
    expect(s.gamesPlayed).toBe(1);
    expect(s.wins).toBe(0);
    expect(s.distribution.every((n) => n === 0)).toBe(true);
  });

  it('is idempotent for the same puzzle', () => {
    // Refreshing on the win screen must not inflate the streak.
    const once = recordResult(emptyStats(), game(1, 'won'));
    expect(recordResult(once, game(1, 'won'))).toEqual(once);
  });

  it('builds a streak across consecutive puzzles', () => {
    const s = play(emptyStats(), game(1, 'won'), game(2, 'won'), game(3, 'won'));
    expect(s.currentStreak).toBe(3);
    expect(s.maxStreak).toBe(3);
  });

  it('breaks the streak on a loss', () => {
    const s = play(emptyStats(), game(1, 'won'), game(2, 'won'), game(3, 'lost'));
    expect(s.currentStreak).toBe(0);
    expect(s.maxStreak).toBe(2);
  });

  it('breaks the streak on a skipped day', () => {
    // Puzzle 4 is missed entirely; 5 starts a new streak rather than continuing.
    const s = play(emptyStats(), game(1, 'won'), game(2, 'won'), game(5, 'won'));
    expect(s.currentStreak).toBe(1);
    expect(s.maxStreak).toBe(2);
  });

  it('remembers the best streak after a break', () => {
    const s = play(
      emptyStats(),
      game(1, 'won'), game(2, 'won'), game(3, 'won'),
      game(4, 'lost'),
      game(5, 'won'),
    );
    expect(s.currentStreak).toBe(1);
    expect(s.maxStreak).toBe(3);
  });

  it('a win after a loss on the very next day starts at 1, not 2', () => {
    const s = play(emptyStats(), game(1, 'lost'), game(2, 'won'));
    expect(s.currentStreak).toBe(1);
  });

  it('never writes outside the histogram', () => {
    // MAX_ATTEMPTS is provisional (planning.md 2.5.1); a stored game from a
    // build with more lives must not corrupt the array.
    const s = recordResult(emptyStats(), game(1, 'won', MAX_ATTEMPTS + 3));
    expect(s.distribution).toHaveLength(MAX_ATTEMPTS);
    expect(s.distribution.every((n) => n === 0)).toBe(true);
  });
});

describe('winPercent', () => {
  it('is 0 before anything is played, not NaN', () => {
    expect(winPercent(emptyStats())).toBe(0);
  });

  it('rounds to whole numbers', () => {
    const s = play(emptyStats(), game(1, 'won'), game(2, 'lost'), game(3, 'won'));
    expect(winPercent(s)).toBe(67);
  });
});
