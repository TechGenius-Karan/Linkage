/**
 * Domain tier (planning.md 4.1). Pure types — no React, no DOM, no fetch.
 *
 * These describe the game as a set of rules, not as a screen. Everything the
 * client knows about a puzzle lives here, and both other tiers depend on this
 * file rather than the other way round.
 */

/** Structural. Changing it touches the solver, the exporter and the board. */
export const CHAIN_LENGTH = 4;

/**
 * Provisional (planning.md 2.5.1). Presented as hearts, never as a counter.
 * Settled at the Phase 5 playtest gate from observed win rate, not guessed —
 * three proved too harsh and six starts to make mechanical probing viable.
 */
export const MAX_ATTEMPTS = 5;

/** Spec allows 10–12; the generator falls back to 10 when safe distractors run short. */
export const BANK_MIN = 10;
export const BANK_MAX = 12;

export const SCHEMA_VERSION = 1;

/**
 * Theme preference (docs/design.md 2.1).
 *
 * Read twice: once by the settings control, and once by an inline script in
 * `index.html` that runs before first paint. The second reader is the reason
 * this constant exists -- a rename that only updated the TypeScript would
 * leave the page flashing the wrong background with nothing failing.
 * `tests/theme.test.ts` asserts the two agree.
 */
export const THEME_KEY = 'linkage:v1:theme';

/** `system` means "follow the OS", and is the absence of an override. */
export type ThemePreference = 'light' | 'dark' | 'system';

/** First puzzle's date. Month is 1-indexed here and converted at the boundary. */
export const EPOCH_DATE = '2026-10-01';

export interface Puzzle {
  schemaVersion: number;
  id: number;
  date: string;
  start: string;
  end: string;
  solution: string[];
  bank: string[];
}

export type GameStatus = 'playing' | 'won' | 'lost';

export interface Attempt {
  tiles: string[];
  /** 0..CHAIN_LENGTH — the only thing a player ever learns (planning.md 2.5). */
  correctCount: number;
}

export interface GameState {
  puzzleId: number;
  /** Length CHAIN_LENGTH. `null` is an empty slot. */
  slots: (string | null)[];
  attempts: Attempt[];
  status: GameStatus;
  /** Tap-to-place selection. Never persisted as part of a finished game. */
  selectedTile: string | null;
}

export type Action =
  | { type: 'SELECT_TILE'; tileId: string }
  | { type: 'PLACE_TILE'; slot: number }
  | { type: 'MOVE_TILE'; from: number; to: number }
  | { type: 'REMOVE_TILE'; slot: number }
  | { type: 'SUBMIT' }
  | { type: 'RESTORE'; state: GameState };

export interface Stats {
  gamesPlayed: number;
  wins: number;
  currentStreak: number;
  maxStreak: number;
  /** Index 0 is a win in one attempt; length MAX_ATTEMPTS. */
  distribution: number[];
  lastCompletedId: number | null;
}

/**
 * Thrown when a puzzle genuinely does not exist — before launch, or once the
 * archive runs dry. Distinct from a network failure on purpose: one wants a
 * friendly "no puzzle today", the other wants a retry button (planning.md 8.7).
 */
export class PuzzleNotFound extends Error {
  constructor(public readonly date: string) {
    super(`No puzzle for ${date}`);
    this.name = 'PuzzleNotFound';
  }
}

/** Thrown when a payload exists but does not match the contract (planning.md 3.1). */
export class PuzzleInvalid extends Error {
  constructor(reason: string) {
    super(`Malformed puzzle: ${reason}`);
    this.name = 'PuzzleInvalid';
  }
}
