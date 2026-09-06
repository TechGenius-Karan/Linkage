/**
 * The runtime guard (planning.md 8.4).
 *
 * This is a trust boundary: payloads arrive over the network and are decoded
 * with a codec that is deliberately not authenticated. Each case below is a
 * malformed puzzle that would otherwise render as a broken or unwinnable game
 * rather than as an error.
 */

import { describe, expect, it } from 'vitest';
import { validatePuzzle } from '../src/data/httpPuzzleRepository';
import { PuzzleInvalid } from '../src/engine/types';

const valid = {
  schemaVersion: 1,
  id: 1,
  date: '2026-10-01',
  start: 'whale',
  end: 'wings',
  solution: ['ocean', 'blue', 'sky', 'birds'],
  bank: ['sea', 'ocean', 'cloud', 'sky', 'shark', 'blue', 'nest', 'wave', 'birds', 'color', 'feathers'],
};

const withOverride = (patch: Record<string, unknown>) => ({ ...valid, ...patch });

describe('validatePuzzle', () => {
  it('accepts a well-formed puzzle', () => {
    expect(validatePuzzle(valid)).toEqual(valid);
  });

  it('drops unknown fields rather than passing them through', () => {
    // `meta` is stripped at export (planning.md 3.1); if one ever slips into a
    // payload it must not reach the UI.
    const result = validatePuzzle(withOverride({ meta: { qualityScore: 0.9 } }));
    expect(result).not.toHaveProperty('meta');
  });

  it.each([
    ['not an object', null],
    ['a string', 'whale'],
    ['a wrong schemaVersion', withOverride({ schemaVersion: 2 })],
    ['a non-integer id', withOverride({ id: 1.5 })],
    ['a zero id', withOverride({ id: 0, date: '2026-09-30' })],
    ['a non-string date', withOverride({ date: 20261001 })],
    ['a short solution', withOverride({ solution: ['ocean', 'blue', 'sky'] })],
    ['a long solution', withOverride({ solution: ['ocean', 'blue', 'sky', 'birds', 'nest'] })],
    ['a non-string in the solution', withOverride({ solution: ['ocean', 'blue', 'sky', 7] })],
  ])('rejects %s', (_label, input) => {
    expect(() => validatePuzzle(input)).toThrow(PuzzleInvalid);
  });

  it('rejects a bank that is too small', () => {
    expect(() => validatePuzzle(withOverride({ bank: valid.bank.slice(0, 9) }))).toThrow(
      /bank has 9 tiles/,
    );
  });

  it('rejects a bank that is too large', () => {
    const bank = [...valid.bank, 'reef', 'kite'];
    expect(() => validatePuzzle(withOverride({ bank }))).toThrow(/bank has 13 tiles/);
  });

  it('rejects duplicate bank words', () => {
    // Two identical tiles are indistinguishable, and the word IS the tile id
    // (planning.md 3.1.1) — so this would make the board ambiguous.
    const bank = [...valid.bank.slice(0, 10), 'ocean'];
    expect(() => validatePuzzle(withOverride({ bank }))).toThrow(/duplicate/);
  });

  it('rejects a solution word missing from the bank', () => {
    const bank = valid.bank.map((w) => (w === 'sky' ? 'reef' : w));
    expect(() => validatePuzzle(withOverride({ bank }))).toThrow(/absent from bank: sky/);
  });

  it('rejects an id that disagrees with its date', () => {
    // A drift here would print the wrong puzzle number in every share
    // (planning.md 3.1) — invisible until it is everywhere.
    expect(() => validatePuzzle(withOverride({ id: 5 }))).toThrow(/implies 2026-10-05/);
  });

  it('rejects a payload served under a different date than it claims', () => {
    expect(() => validatePuzzle(valid, '2026-10-02')).toThrow(/served as 2026-10-02/);
  });

  it('accepts a payload served under its own date', () => {
    expect(validatePuzzle(valid, '2026-10-01')).toEqual(valid);
  });
});
