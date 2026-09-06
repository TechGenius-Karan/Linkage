/**
 * Domain tier. The interfaces the data tier must satisfy (planning.md 5, D).
 *
 * These live here, in the logic tier, rather than beside their implementations.
 * That is Dependency Inversion in its load-bearing form: the logic owns the
 * contract and the data tier conforms to it, so swapping static files for a
 * Worker endpoint later touches exactly one file and no consumer.
 *
 * Two narrow ports rather than one fat `GameService` (planning.md 5, I) —
 * nothing depends on methods it does not call.
 */

import type { GameState, Puzzle, Stats } from './types';

export interface PuzzleRepository {
  /**
   * Rejects with `PuzzleNotFound` when the puzzle does not exist, and with
   * `PuzzleInvalid` when it exists but is malformed. Every implementation
   * must use the same error types — a stub that resolved `null` instead
   * would break every consumer relying on the contract (planning.md 5, L).
   */
  load(id: number, date: string): Promise<Puzzle>;
}

export interface ProgressStore {
  readProgress(id: number): GameState | null;
  writeProgress(id: number, state: GameState): void;
  readStats(): Stats;
  writeStats(stats: Stats): void;
}
