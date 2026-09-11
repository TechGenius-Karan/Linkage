/**
 * Streaks and the time distribution (planning.md 2.8, 2.5.2).
 *
 * The streak rule is the one people notice being wrong, because a broken
 * streak is the thing a daily-game player is most attached to.
 */

import { describe, expect, it } from 'vitest';
import { emptyStats, recordResult, TIME_BUCKETS_MS } from '../src/engine/stats';
import type { GameState, Stats } from '../src/engine/types';

const NOW = 1_700_000_000_000;

const game = (puzzleId: number, status: 'won' | 'playing', elapsedMs = 10_000): GameState => ({
  puzzleId,
  slots: ['a', 'b', 'c', 'd'],
  attempts: [{ tiles: [], correctCount: 0 }],
  status,
  selectedTile: null,
  hintsUsed: [],
  startedAt: NOW,
  pausedAt: null,
  totalPausedMs: 0,
  hintPenaltyMs: 0,
  finishedAt: status === 'won' ? NOW + elapsedMs : null,
});

const play = (stats: Stats, ...games: GameState[]) => games.reduce(recordResult, stats);

describe('recordResult', () => {
  it('ignores a game still in progress', () => {
    expect(recordResult(emptyStats(), game(1, 'playing'))).toEqual(emptyStats());
  });

  it('counts a win', () => {
    const s = recordResult(emptyStats(), game(1, 'won', 45_000));
    expect(s.gamesPlayed).toBe(1);
    expect(s.currentStreak).toBe(1);
    expect(s.maxStreak).toBe(1);
    expect(s.bestTimeMs).toBe(45_000);
    expect(s.totalTimeMs).toBe(45_000);
  });

  it('buckets a win by elapsed time', () => {
    // TIME_BUCKETS_MS[0] is the first bucket's upper bound.
    const s = recordResult(emptyStats(), game(1, 'won', TIME_BUCKETS_MS[0]! - 1));
    expect(s.distribution[0]).toBe(1);
    expect(s.distribution.slice(1).every((n) => n === 0)).toBe(true);
  });

  it('puts anything past the last boundary in the catch-all bucket', () => {
    const s = recordResult(emptyStats(), game(1, 'won', TIME_BUCKETS_MS.at(-1)! + 999_000));
    expect(s.distribution.at(-1)).toBe(1);
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

  it('breaks the streak on a skipped day', () => {
    // Puzzle 4 is missed entirely; 5 starts a new streak rather than continuing.
    const s = play(emptyStats(), game(1, 'won'), game(2, 'won'), game(5, 'won'));
    expect(s.currentStreak).toBe(1);
    expect(s.maxStreak).toBe(2);
  });

  it('tracks the best time across multiple wins', () => {
    const s = play(emptyStats(), game(1, 'won', 60_000), game(2, 'won', 20_000), game(3, 'won', 40_000));
    expect(s.bestTimeMs).toBe(20_000);
    expect(s.totalTimeMs).toBe(120_000);
  });
});
