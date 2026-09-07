/**
 * Domain tier. Streaks and the distribution histogram (planning.md 2.8).
 *
 * Pure: takes the old stats and a finished game, returns new stats. Nothing
 * here reads storage — `ProgressStore` does that, and this decides what to
 * store.
 */

import { MAX_ATTEMPTS, type GameState, type Stats } from './types';

export function emptyStats(): Stats {
  return {
    gamesPlayed: 0,
    wins: 0,
    currentStreak: 0,
    maxStreak: 0,
    distribution: Array<number>(MAX_ATTEMPTS).fill(0),
    lastCompletedId: null,
  };
}

/**
 * Fold a finished game into the running stats.
 *
 * Idempotent by puzzle id: recording the same puzzle twice — which a refresh
 * on the win screen would otherwise do — leaves the stats unchanged.
 */
export function recordResult(stats: Stats, game: GameState): Stats {
  if (game.status === 'playing') return stats;
  if (stats.lastCompletedId === game.puzzleId) return stats;

  const won = game.status === 'won';

  // A streak survives only across consecutive puzzle numbers. Missing a day
  // breaks it, which is the whole point of a daily game.
  const consecutive =
    stats.lastCompletedId !== null && game.puzzleId === stats.lastCompletedId + 1;
  const currentStreak = won ? (consecutive ? stats.currentStreak + 1 : 1) : 0;

  const distribution = [...stats.distribution];
  if (won) {
    // attempts.length is 1-based for a player; the array is 0-based.
    const bucket = game.attempts.length - 1;
    if (bucket >= 0 && bucket < distribution.length) {
      distribution[bucket] = (distribution[bucket] ?? 0) + 1;
    }
  }

  return {
    gamesPlayed: stats.gamesPlayed + 1,
    wins: stats.wins + (won ? 1 : 0),
    currentStreak,
    maxStreak: Math.max(stats.maxStreak, currentStreak),
    distribution,
    lastCompletedId: game.puzzleId,
  };
}

/** Whole-number percent, 0 when nothing has been played. */
export function winPercent(stats: Stats): number {
  if (stats.gamesPlayed === 0) return 0;
  return Math.round((stats.wins / stats.gamesPlayed) * 100);
}
