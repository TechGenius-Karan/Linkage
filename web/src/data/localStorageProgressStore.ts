/**
 * Data tier. Persistence (planning.md 2.8).
 *
 * Every access is wrapped: Safari private mode throws on write, storage can be
 * disabled outright, and a `QuotaExceededError` is a real thing that happens.
 * None of those may break the game — a player who cannot save should still be
 * able to play, so a failed store degrades to in-memory rather than throwing.
 *
 * Reads are equally defensive. A corrupt, absent, or half-written value yields
 * a fresh game, never a crash.
 */

import type { ProgressStore } from '../engine/ports';
import { MAX_ATTEMPTS, type GameState, type Stats } from '../engine/types';

const PREFIX = 'linkage:v1';
const STATS_KEY = `${PREFIX}:stats`;
const PROGRESS_PREFIX = `${PREFIX}:progress:`;

/** Progress entries older than this are pruned on load (planning.md 2.8). */
const PROGRESS_KEEP_DAYS = 7;

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

/** Shape check for anything read back out of storage — it is not trusted. */
function isGameState(v: unknown): v is GameState {
  if (typeof v !== 'object' || v === null) return false;
  const s = v as Record<string, unknown>;
  return (
    typeof s['puzzleId'] === 'number' &&
    Array.isArray(s['slots']) &&
    Array.isArray(s['attempts']) &&
    (s['status'] === 'playing' || s['status'] === 'won' || s['status'] === 'lost')
  );
}

function isStats(v: unknown): v is Stats {
  if (typeof v !== 'object' || v === null) return false;
  const s = v as Record<string, unknown>;
  return (
    typeof s['gamesPlayed'] === 'number' &&
    typeof s['wins'] === 'number' &&
    typeof s['currentStreak'] === 'number' &&
    typeof s['maxStreak'] === 'number' &&
    Array.isArray(s['distribution'])
  );
}

export class LocalStorageProgressStore implements ProgressStore {
  /** Used when localStorage is unavailable, so the session still works. */
  private readonly fallback = new Map<string, string>();
  private storageWorks = true;

  constructor() {
    this.prune();
  }

  private read(key: string): string | null {
    try {
      const stored = localStorage.getItem(key);
      if (stored !== null) return stored;
    } catch {
      this.storageWorks = false;
    }
    // Falls through on both a throw and a miss. A quota-exceeded write does
    // not throw on the way back out -- it simply returns null -- so consulting
    // the in-memory fallback only in the catch would lose the current game for
    // exactly the players the fallback exists to serve.
    return this.fallback.get(key) ?? null;
  }

  private write(key: string, value: string): void {
    try {
      localStorage.setItem(key, value);
    } catch {
      // Quota exceeded, private mode, or storage disabled. Keep playing.
      this.storageWorks = false;
      this.fallback.set(key, value);
    }
  }

  private parse<T>(raw: string | null, guard: (v: unknown) => v is T): T | null {
    if (raw === null) return null;
    try {
      const parsed: unknown = JSON.parse(raw);
      return guard(parsed) ? parsed : null;
    } catch {
      return null;
    }
  }

  readProgress(id: number): GameState | null {
    return this.parse(this.read(PROGRESS_PREFIX + id), isGameState);
  }

  writeProgress(id: number, state: GameState): void {
    this.write(PROGRESS_PREFIX + id, JSON.stringify(state));
  }

  readStats(): Stats {
    const stats = this.parse(this.read(STATS_KEY), isStats);
    if (stats === null) return emptyStats();
    // A distribution of the wrong length would break the histogram if
    // MAX_ATTEMPTS ever changes — which planning.md 2.5.1 says it will.
    if (stats.distribution.length !== MAX_ATTEMPTS) {
      const fixed = Array<number>(MAX_ATTEMPTS).fill(0);
      stats.distribution.forEach((n, i) => {
        if (i < MAX_ATTEMPTS) fixed[i] = typeof n === 'number' ? n : 0;
      });
      stats.distribution = fixed;
    }
    return stats;
  }

  writeStats(stats: Stats): void {
    this.write(STATS_KEY, JSON.stringify(stats));
  }

  /** True when writes are actually landing. Exposed for a settings panel. */
  get persistent(): boolean {
    return this.storageWorks;
  }

  /**
   * Drop progress for puzzles more than a week old. Without this, a daily game
   * accumulates one dead key per day forever.
   */
  private prune(): void {
    // `length` + `key(i)` is the actual Storage API. `Object.keys(localStorage)`
    // happens to work in browsers because Storage exposes entries as own
    // properties, but it is not specified and it is not what a conforming
    // implementation has to provide.
    let keys: string[];
    try {
      keys = [];
      for (let i = 0; i < localStorage.length; i++) {
        const k = localStorage.key(i);
        if (k !== null) keys.push(k);
      }
    } catch {
      this.storageWorks = false;
      return;
    }
    // Progress keys are only useful for a puzzle still in play, and puzzle ids
    // are sequential, so "old" is decidable without storing a timestamp.
    const ids = keys
      .filter((k) => k.startsWith(PROGRESS_PREFIX))
      .map((k) => ({ key: k, id: Number(k.slice(PROGRESS_PREFIX.length)) }))
      .filter((e) => Number.isFinite(e.id));
    if (ids.length === 0) return;

    const newest = Math.max(...ids.map((e) => e.id));
    for (const entry of ids) {
      if (newest - entry.id >= PROGRESS_KEEP_DAYS) {
        try {
          localStorage.removeItem(entry.key);
        } catch {
          this.storageWorks = false;
          return;
        }
      }
    }
  }
}
