/**
 * The cross-language guarantee (planning.md Risk #3).
 *
 * This does not test the decoder against itself — a round-trip written in one
 * language proves nothing about agreement with the other. It decodes a payload
 * **Python produced**, so a divergence in UTF-8 handling or base64 byte
 * handling fails here rather than on a player's phone.
 *
 * Regenerate the fixture with `linkage emit-codec-fixture`.
 */

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { decode } from '../src/data/codec';

const FIXTURE = fileURLToPath(
  new URL('../../engine/fixtures/codec-fixture.json', import.meta.url),
);

interface Fixture {
  note: string;
  key: string;
  encoded: string;
  expected: Record<string, unknown>;
}

const fixture = JSON.parse(readFileSync(FIXTURE, 'utf-8')) as Fixture;

describe('codec', () => {
  it('decodes the payload Python encoded', () => {
    expect(decode(fixture.encoded, fixture.key)).toEqual(fixture.expected);
  });

  it('survives multibyte UTF-8', () => {
    // The whole reason the fixture carries a probe: `atob` hands back a binary
    // string, and treating it as text mangles every non-ASCII sequence.
    const probe = fixture.expected['_utf8Probe'] as string;
    // Non-ASCII by construction -- if the fixture ever lost its multibyte
    // characters this test would still pass while proving nothing.
    expect([...probe].some((c) => c.codePointAt(0)! > 127)).toBe(true);

    const decoded = decode(fixture.encoded, fixture.key) as Record<string, unknown>;
    expect(decoded['_utf8Probe']).toBe(probe);
  });

  it('uses the puzzle date as the key', () => {
    expect(fixture.key).toBe(fixture.expected['date']);
  });

  it('throws on the wrong key rather than returning nonsense', () => {
    expect(() => decode(fixture.encoded, '1999-01-01')).toThrow();
  });

  it('rejects an empty key', () => {
    expect(() => decode(fixture.encoded, '')).toThrow(/key must not be empty/);
  });
});
