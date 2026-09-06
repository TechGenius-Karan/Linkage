/**
 * Domain tier. Which puzzle is "today" (planning.md 8.3).
 *
 * The trap this file exists to avoid: subtracting raw timestamps drifts by one
 * puzzle for half the year in every DST-observing timezone, and does it
 * silently. We read **local** calendar fields and do the arithmetic in **UTC**,
 * which normalises DST away entirely — the day count is exact whether or not a
 * 23- or 25-hour day fell in the interval.
 */

import { EPOCH_DATE } from './types';

const MS_PER_DAY = 86_400_000;

/** Parses `YYYY-MM-DD` without going through Date's timezone guessing. */
function parseIsoDate(iso: string): { y: number; m: number; d: number } {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!match) throw new Error(`Not an ISO date: ${iso}`);
  return { y: Number(match[1]), m: Number(match[2]) - 1, d: Number(match[3]) };
}

/**
 * Puzzle number for a moment in the player's local timezone. Puzzle #1 is
 * EPOCH_DATE; the day before it is #0, which callers treat as "not launched".
 */
export function puzzleNumberFor(now: Date, epoch: string = EPOCH_DATE): number {
  const e = parseIsoDate(epoch);
  const a = Date.UTC(e.y, e.m, e.d);
  const b = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate());
  return Math.round((b - a) / MS_PER_DAY) + 1;
}

/** The inverse: the ISO date a puzzle number is scheduled for. */
export function dateForPuzzleNumber(id: number, epoch: string = EPOCH_DATE): string {
  const e = parseIsoDate(epoch);
  const t = new Date(Date.UTC(e.y, e.m, e.d + (id - 1)));
  const y = String(t.getUTCFullYear()).padStart(4, '0');
  const m = String(t.getUTCMonth() + 1).padStart(2, '0');
  const d = String(t.getUTCDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}
