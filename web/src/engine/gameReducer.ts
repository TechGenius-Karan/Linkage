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
  MAX_ATTEMPTS,
  type Action,
  type GameState,
  type Puzzle,
} from './types';

export function initialState(puzzleId: number): GameState {
  return {
    puzzleId,
    slots: Array<string | null>(CHAIN_LENGTH).fill(null),
    attempts: [],
    status: 'playing',
    selectedTile: null,
    hintsUsed: [],
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
        return { ...state, hintsUsed: [...state.hintsUsed, next] };
      }

      case 'SUBMIT': {
        if (state.slots.some((s) => s === null)) return state;
        const tiles = state.slots as string[];

        // Strictly positional, and the count is all the player ever learns.
        let correctCount = 0;
        for (let i = 0; i < CHAIN_LENGTH; i++) {
          if (tiles[i] === puzzle.solution[i]) correctCount++;
        }

        const attempts = [...state.attempts, { tiles: [...tiles], correctCount }];
        const status =
          correctCount === CHAIN_LENGTH
            ? 'won'
            : attempts.length >= MAX_ATTEMPTS
              ? 'lost'
              : 'playing';

        return { ...state, attempts, status, selectedTile: null };
      }
    }
  };
}

/**
 * Hearts still showing.
 *
 * A life is lost by being *wrong*, so the winning guess does not cost one --
 * otherwise a first-try solve renders with a drained heart, which reads as a
 * penalty on the one screen people screenshot.
 */
export const livesRemaining = (state: GameState): number => {
  const failed = state.status === 'won' ? state.attempts.length - 1 : state.attempts.length;
  return Math.max(0, MAX_ATTEMPTS - failed);
};

export const hintsRemaining = (state: GameState, puzzle: Puzzle): number =>
  Math.max(0, puzzle.hints.length - state.hintsUsed.length);

export const isBoardFull = (state: GameState): boolean =>
  state.slots.every((s) => s !== null);
