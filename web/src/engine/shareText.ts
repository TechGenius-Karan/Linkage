/**
 * Domain tier. The share card (planning.md 2.5.2, 2.5.3).
 *
 * Local-only: puzzle number, time, hints used. No emoji grid, no backend, no
 * cross-player comparison — v1 deliberately does not have one (planning.md 9).
 */

import { elapsedMs } from './gameReducer';
import type { GameState } from './types';

function formatTime(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, '0')}`;
}

/** Meant for a won game — `state.finishedAt` is what freezes the time reported. */
export function buildShareText(state: GameState): string {
  const time = formatTime(elapsedMs(state, state.finishedAt ?? 0));
  const hints = state.hintsUsed.length;
  const hintNote = hints > 0 ? ` (${hints} hint${hints === 1 ? '' : 's'} used)` : '';
  return `Linkage #${state.puzzleId} — solved in ${time}${hintNote}`;
}
