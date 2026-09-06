/**
 * Data tier. The decoder half of planning.md 3.2.
 *
 * `engine/src/linkage_engine/data/codec.py` is the encoder, and the two must
 * agree **byte for byte**:
 *
 *     encode:  utf8(json) -> XOR with repeating key = utf8(dateISO) -> base64
 *     decode:  base64 -> XOR with same key -> utf8 -> JSON.parse
 *
 * Obfuscation, not encryption. It stops casual DevTools snooping and lets the
 * client fetch ~1 KB instead of a bundle containing every answer. A determined
 * person still recovers it, and that is fine.
 *
 * The failure this file exists to avoid is specific and silent: `atob` returns
 * a **binary string**, one UTF-16 code unit per byte — not text. Decoding it
 * with anything that assumes characters corrupts every multibyte sequence, and
 * a naive ASCII-only test passes anyway. `tests/codec.test.ts` decodes a
 * Python-generated fixture carrying deliberate non-ASCII for exactly this
 * reason (Risk #3).
 */

/** `atob` output -> real bytes. Each code unit is one byte in 0..255. */
function base64ToBytes(b64: string): Uint8Array {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

/** XOR against a repeating key. Its own inverse, same as the Python side. */
function xorBytes(payload: Uint8Array, key: Uint8Array): Uint8Array {
  if (key.length === 0) throw new Error('codec key must not be empty');
  const out = new Uint8Array(payload.length);
  for (let i = 0; i < payload.length; i++) {
    // `!` is safe: both indices are provably in range, but
    // noUncheckedIndexedAccess cannot see that.
    out[i] = payload[i]! ^ key[i % key.length]!;
  }
  return out;
}

export function decode(blob: string, key: string): unknown {
  const scrambled = base64ToBytes(blob);
  const keyBytes = new TextEncoder().encode(key);
  const raw = xorBytes(scrambled, keyBytes);
  // `fatal` so invalid UTF-8 throws instead of silently yielding U+FFFD —
  // a corrupted payload must fail loudly, not render as a puzzle of question marks.
  const text = new TextDecoder('utf-8', { fatal: true }).decode(raw);
  return JSON.parse(text);
}
