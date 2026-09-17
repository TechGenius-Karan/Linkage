/**
 * Domain tier. Streaks and the distribution histogram (planning.md 2.8).
 *
 * Pure: takes the old stats and a finished game, returns new stats. Nothing
 * here reads storage — `ProgressStore` does that, and this decides what to
 * store.
 */

import { elapsedMs } from './gameReducer';
import type { GameState, Stats } from './types';

/**
 * Upper bound in ms of each bucket but the last, which catches everything
 * above. Provisional (planning.md 2.5.2), same spirit as MAX_ATTEMPTS was:
 * these are placeholders pending the Phase 5 playtest data that will show
 * what an actual solve-time distribution looks like.
 */
export const TIME_BUCKETS_MS = [30_000, 60_000, 120_000, 300_000] as const;

export function bucketFor(ms: number): number {
  const i = TIME_BUCKETS_MS.findIndex((upper) => ms <= upper);
  return i === -1 ? TIME_BUCKETS_MS.length : i;
}

/** mm:ss — shared by the share card, the stats modal, and the clipboard text. */
export function formatTime(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, '0')}`;
}

/** e.g. 30_000 -> "30s", 120_000 -> "2m". Short form for a narrow chart label. */
function shortDuration(ms: number): string {
  return ms < 60_000 ? `${ms / 1000}s` : `${ms / 60_000}m`;
}

/** One label per `TIME_BUCKETS_MS` entry, plus the catch-all bucket past the last boundary. */
export const BUCKET_LABELS = TIME_BUCKETS_MS.map((ms) => `<${shortDuration(ms)}`).concat(
  `${shortDuration(TIME_BUCKETS_MS[TIME_BUCKETS_MS.length - 1]!)}+`,
);

export function emptyStats(): Stats {
  return {
    gamesPlayed: 0,
    currentStreak: 0,
    maxStreak: 0,
    bestTimeMs: null,
    totalTimeMs: 0,
    distribution: Array<number>(TIME_BUCKETS_MS.length + 1).fill(0),
    lastCompletedId: null,
  };
}

/**
 * Fold a finished game into the running stats.
 *
 * Idempotent by puzzle id: recording the same puzzle twice — which a refresh
 * on the win screen would otherwise do — leaves the stats unchanged. There is
 * no loss state (planning.md 2.5.2), so every completed game here is a win.
 */
export function recordResult(stats: Stats, game: GameState): Stats {
  if (game.status !== 'won') return stats;
  if (stats.lastCompletedId === game.puzzleId) return stats;

  // A streak survives only across consecutive puzzle numbers. Missing a day
  // breaks it, which is the whole point of a daily game.
  const consecutive =
    stats.lastCompletedId !== null && game.puzzleId === stats.lastCompletedId + 1;
  const currentStreak = consecutive ? stats.currentStreak + 1 : 1;

  // finishedAt is always set on a win, so `now` here is never actually read.
  const time = elapsedMs(game, game.finishedAt ?? 0);
  const distribution = [...stats.distribution];
  const bucket = bucketFor(time);
  distribution[bucket] = (distribution[bucket] ?? 0) + 1;

  return {
    gamesPlayed: stats.gamesPlayed + 1,
    currentStreak,
    maxStreak: Math.max(stats.maxStreak, currentStreak),
    bestTimeMs: stats.bestTimeMs === null ? time : Math.min(stats.bestTimeMs, time),
    totalTimeMs: stats.totalTimeMs + time,
    distribution,
    lastCompletedId: game.puzzleId,
  };
}
