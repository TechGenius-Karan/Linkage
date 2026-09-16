/**
 * Domain tier. What day it is for the player, right now (planning.md 8.3).
 *
 * A puzzle's number is never guessed here -- it comes off the puzzle itself
 * once fetched, because the archive may skip a day (planning.md 3.3) and an
 * id is no longer a pure function of a date. All this module owns is "what
 * is today's date", which is a formatting question, not an arithmetic one:
 * read **local** calendar fields directly, so nothing here can drift the way
 * subtracting raw timestamps across a DST boundary would.
 */

/** Today's date in the player's local timezone, as `YYYY-MM-DD`. */
export function todayIsoDate(now: Date): string {
  const y = String(now.getFullYear()).padStart(4, '0');
  const m = String(now.getMonth() + 1).padStart(2, '0');
  const d = String(now.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}
