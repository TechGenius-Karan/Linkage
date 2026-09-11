/**
 * Domain tier. Every rule of the game, in one pure function (planning.md 8.2).
 *
 * The reducer is **curried over the puzzle** rather than holding it in state.
 * That keeps the solution out of `GameState` — which is serialised into
 * `localStorage` and readable in React DevTools — while leaving the reducer a
 * plain `(state, action) => state` for `useReducer`. Every test here is a
 * function call: no React, no rendering, no mocks.
 *
 * Nothing in this file knows that dragging, double-tapping or keyboards exist.
 * The presentation tier translates gestures into these actions and no further
 * (planning.md 2.4).
 */

import {
  CHAIN_LENGTH,
  HINT_TIME_PENALTY_MS,
  type Action,
  type GameState,
  type Puzzle,
} from './types';

export function initialState(puzzleId: number, now: number): GameState {
  return {
    puzzleId,
    slots: Array<string | null>(CHAIN_LENGTH).fill(null),
    attempts: [],
    status: 'playing',
    selectedTile: null,
    hintsUsed: [],
    startedAt: now,
    pausedAt: null,
    totalPausedMs: 0,
    hintPenaltyMs: 0,
    finishedAt: null,
  };
}

const inBounds = (i: number): boolean =>
  Number.isInteger(i) && i >= 0 && i < CHAIN_LENGTH;

export function makeGameReducer(puzzle: Puzzle) {
  return function reduce(state: GameState, action: Action): GameState {
    // RESTORE is the one action a finished game still accepts — it is how a
    // completed board comes back after a refresh.
    if (action.type === 'RESTORE') return action.state;
    if (state.status !== 'playing') return state;

    switch (action.type) {
      case 'SELECT_TILE': {
        // A tile already on the board is not selectable; it is moved with
        // MOVE_TILE or returned with REMOVE_TILE.
        if (state.slots.includes(action.tileId)) return state;
        if (!puzzle.bank.includes(action.tileId)) return state;
        return {
          ...state,
          selectedTile: state.selectedTile === action.tileId ? null : action.tileId,
        };
      }

      case 'PLACE_TILE': {
        if (!inBounds(action.slot)) return state;
        const held = state.selectedTile;
        if (held === null) return state;

        const slots = [...state.slots];
        const displaced = slots[action.slot] ?? null;
        const from = slots.indexOf(held);

        slots[action.slot] = held;
        // Moving a tile that was already on the board swaps the two rather
        // than duplicating it — a tile exists in exactly one place.
        if (from !== -1 && from !== action.slot) slots[from] = displaced;

        return { ...state, slots, selectedTile: null };
      }

      case 'MOVE_TILE': {
        if (!inBounds(action.from) || !inBounds(action.to)) return state;
        if (action.from === action.to) return state;

        const slots = [...state.slots];
        const a = slots[action.from] ?? null;
        const b = slots[action.to] ?? null;
        if (a === null && b === null) return state;
        slots[action.from] = b;
        slots[action.to] = a;

        // Deliberately does NOT clear the selection: reordering the ladder
        // while holding a bank tile is a reasonable thing to want to do.
        return { ...state, slots };
      }

      case 'REMOVE_TILE': {
        if (!inBounds(action.slot)) return state;
        if (state.slots[action.slot] === null) return state;
        const slots = [...state.slots];
        slots[action.slot] = null;
        return { ...state, slots };
      }

      case 'TAKE_HINT': {
        // The next unused hint, in the order the engine ranked them
        // (planning.md 2.5.3). Confirms membership; says nothing about position,
        // and places nothing on the board.
        const next = puzzle.hints.find((w) => !state.hintsUsed.includes(w));
        if (next === undefined) return state;
        return {
          ...state,
          hintsUsed: [...state.hintsUsed, next],
          hintPenaltyMs: state.hintPenaltyMs + HINT_TIME_PENALTY_MS,
        };
      }

      case 'SUBMIT': {
        if (state.slots.some((s) => s === null)) return state;
        const tiles = state.slots as string[];

        // Strictly positional, and the count is all the player ever learns.
        let correctCount = 0;
        for (let i = 0; i < CHAIN_LENGTH; i++) {
          if (tiles[i] === puzzle.solution[i]) correctCount++;
        }

        // Guesses are free (planning.md 2.5.2) — there is no losing branch.
        const attempts = [...state.attempts, { tiles: [...tiles], correctCount }];
        const won = correctCount === CHAIN_LENGTH;

        return {
          ...state,
          attempts,
          status: won ? 'won' : 'playing',
          selectedTile: null,
          finishedAt: won ? action.now : null,
        };
      }

      case 'PAUSE': {
        if (state.pausedAt !== null) return state;
        return { ...state, pausedAt: action.now };
      }

      case 'RESUME': {
        if (state.pausedAt === null) return state;
        return {
          ...state,
          pausedAt: null,
          totalPausedMs: state.totalPausedMs + (action.now - state.pausedAt),
        };
      }
    }
  };
}

/**
 * Elapsed play time, in ms, as of `now` (planning.md 2.5.2).
 *
 * `now` is a parameter rather than a call to `Date.now()` so this stays a
 * pure function of its arguments — the tier boundary (planning.md 4.1)
 * forbids the engine from reading the clock itself. Frozen once the game is
 * won (`finishedAt` set) and while paused (`pausedAt` set); a hint's penalty
 * is folded into `hintPenaltyMs` immediately, which is what makes the timer
 * visibly jump the instant a hint is taken rather than only on the next tick.
 */
export const elapsedMs = (state: GameState, now: number): number => {
  const end = state.finishedAt ?? now;
  const ongoingPause = state.pausedAt !== null ? end - state.pausedAt : 0;
  const raw = end - state.startedAt - state.totalPausedMs - ongoingPause;
  return Math.max(0, raw) + state.hintPenaltyMs;
};

export const hintsRemaining = (state: GameState, puzzle: Puzzle): number =>
  Math.max(0, puzzle.hints.length - state.hintsUsed.length);

export const isBoardFull = (state: GameState): boolean =>
  state.slots.every((s) => s !== null);
