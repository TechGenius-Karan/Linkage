/**
 * The DST trap (planning.md 8.3, Risk #6).
 *
 * Subtracting raw timestamps drifts by one puzzle for half the year in every
 * DST-observing timezone, and does it silently — the most expensive kind of
 * bug this client can have, because every share text would be wrong and
 * nobody would know why. A boundary test is mandatory.
 */

import { describe, expect, it } from 'vitest';
import { dateForPuzzleNumber, puzzleNumberFor } from '../src/engine/dailyIndex';
import { EPOCH_DATE } from '../src/engine/types';

/** Local midnight, built from calendar fields exactly as a browser would. */
const localDay = (y: number, m: number, d: number, h = 12) => new Date(y, m - 1, d, h);

describe('puzzleNumberFor', () => {
  it('numbers the epoch as puzzle 1', () => {
    expect(puzzleNumberFor(localDay(2026, 10, 1))).toBe(1);
  });

  it('advances by one per calendar day', () => {
    expect(puzzleNumberFor(localDay(2026, 10, 2))).toBe(2);
    expect(puzzleNumberFor(localDay(2026, 10, 31))).toBe(31);
    expect(puzzleNumberFor(localDay(2026, 11, 1))).toBe(32);
  });

  it('is 0 or less before launch, so callers can show "not yet"', () => {
    expect(puzzleNumberFor(localDay(2026, 9, 30))).toBe(0);
    expect(puzzleNumberFor(localDay(2026, 9, 6))).toBeLessThan(1);
  });

  it('does not drift across a spring-forward boundary', () => {
    // US DST begins 2027-03-14; the local day is 23 hours long. Raw millisecond
    // subtraction would round this pair to the same number.
    const before = puzzleNumberFor(localDay(2027, 3, 13));
    const after = puzzleNumberFor(localDay(2027, 3, 14));
    expect(after - before).toBe(1);
  });

  it('does not drift across a fall-back boundary', () => {
    // 2027-11-07 is 25 hours long in the US.
    const before = puzzleNumberFor(localDay(2027, 11, 6));
    const after = puzzleNumberFor(localDay(2027, 11, 7));
    expect(after - before).toBe(1);
  });

  it('is the same number at 00:01 and 23:59 of one local day', () => {
    expect(puzzleNumberFor(new Date(2027, 2, 14, 0, 1))).toBe(
      puzzleNumberFor(new Date(2027, 2, 14, 23, 59)),
    );
  });

  it('stays exact across a leap day and a full year', () => {
    // 2028 is a leap year: 2027-10-01 -> 2028-10-01 is 366 days.
    const a = puzzleNumberFor(localDay(2027, 10, 1));
    const b = puzzleNumberFor(localDay(2028, 10, 1));
    expect(b - a).toBe(366);
  });
});

describe('dateForPuzzleNumber', () => {
  it('inverts puzzleNumberFor', () => {
    expect(dateForPuzzleNumber(1)).toBe(EPOCH_DATE);
    for (let id = 1; id <= 400; id++) {
      const iso = dateForPuzzleNumber(id);
      const [y, m, d] = iso.split('-').map(Number) as [number, number, number];
      expect(puzzleNumberFor(localDay(y, m, d))).toBe(id);
    }
  });

  it('pads months and days', () => {
    expect(dateForPuzzleNumber(1)).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(dateForPuzzleNumber(8)).toBe('2026-10-08');
  });

  it('crosses a year boundary correctly', () => {
    expect(dateForPuzzleNumber(93)).toBe('2027-01-01');
  });
});
