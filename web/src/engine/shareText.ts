/**
 * Domain tier. The share card (planning.md 2.5.2, 2.5.3).
 *
 * Local-only: puzzle number, time, hints used. No emoji grid, no backend, no
 * cross-player comparison — v1 deliberately does not have one (planning.md 9).
 */

import { formatTime } from './stats';
import { elapsedMs } from './gameReducer';
import type { GameState } from './types';

/** Only ever appended to the clipboard text (`buildShareText`) — never shown
 * on the on-screen card (`buildShareParts`), so the modal stays a game
 * summary and the link rides along silently on paste. */
const SITE_URL = 'https://linkage-daily.netlify.app';

export interface ShareParts {
  headline: string;
  /** null when no hint was used, so a layout can drop the line entirely. */
  hintNote: string | null;
}

/** Meant for a won game — `state.finishedAt` is what freezes the time reported. */
export function buildShareParts(state: GameState): ShareParts {
  const time = formatTime(elapsedMs(state, state.finishedAt ?? 0));
  const hints = state.hintsUsed.length;
  return {
    headline: `Linkage #${state.puzzleId} — solved in ${time}`,
    hintNote: hints > 0 ? `(${hints} hint${hints === 1 ? '' : 's'} used)` : null,
  };
}

/** The single pasteable line — what a clipboard paste must look like, unlike
 * the on-screen card, which breaks the hint note onto its own row. */
export function buildShareText(state: GameState): string {
  const { headline, hintNote } = buildShareParts(state);
  const line = hintNote === null ? headline : `${headline} ${hintNote}`;
  return `${line}\n${SITE_URL}`;
}
