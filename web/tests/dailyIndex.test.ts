/**
 * The DST trap (planning.md 8.3, Risk #6).
 *
 * Formatting local calendar fields directly can't drift the way subtracting
 * raw timestamps across a DST boundary would — but the boundary test stays,
 * because "obviously can't be wrong" is exactly the kind of claim a bug like
 * that hides behind.
 */

import { describe, expect, it } from 'vitest';
import { todayIsoDate } from '../src/engine/dailyIndex';

describe('todayIsoDate', () => {
  it('formats calendar fields as YYYY-MM-DD', () => {
    expect(todayIsoDate(new Date(2026, 9, 1, 12))).toBe('2026-10-01');
  });

  it('pads single-digit months and days', () => {
    expect(todayIsoDate(new Date(2026, 0, 5, 12))).toBe('2026-01-05');
  });

  it('is the same date at 00:01 and 23:59 of one local day', () => {
    expect(todayIsoDate(new Date(2027, 2, 14, 0, 1))).toBe(
      todayIsoDate(new Date(2027, 2, 14, 23, 59)),
    );
  });

  it('does not drift across a spring-forward boundary', () => {
    // US DST begins 2027-03-14; the local day is 23 hours long.
    expect(todayIsoDate(new Date(2027, 2, 13, 12))).toBe('2027-03-13');
    expect(todayIsoDate(new Date(2027, 2, 14, 12))).toBe('2027-03-14');
  });

  it('does not drift across a fall-back boundary', () => {
    // 2027-11-07 is 25 hours long in the US.
    expect(todayIsoDate(new Date(2027, 10, 6, 12))).toBe('2027-11-06');
    expect(todayIsoDate(new Date(2027, 10, 7, 12))).toBe('2027-11-07');
  });

  it('crosses a year boundary correctly', () => {
    expect(todayIsoDate(new Date(2026, 11, 31, 12))).toBe('2026-12-31');
    expect(todayIsoDate(new Date(2027, 0, 1, 12))).toBe('2027-01-01');
  });
});
