/**
 * Data tier. Fetch, decode, validate (planning.md 8.4).
 *
 * Implements `PuzzleRepository`, which is declared in the domain tier. This
 * file is the only thing that knows puzzles arrive over HTTP as obfuscated
 * per-day JSON; swapping to a Worker endpoint replaces this class and nothing
 * else.
 */

import { dateForPuzzleNumber } from '../engine/dailyIndex';
import { decode } from './codec';
import type { PuzzleRepository } from '../engine/ports';
import {
  BANK_MAX,
  BANK_MIN,
  CHAIN_LENGTH,
  PuzzleInvalid,
  PuzzleNotFound,
  SCHEMA_VERSION,
  type Puzzle,
} from '../engine/types';

/**
 * A hand-written runtime guard (planning.md 8.4). A schema library would be a
 * dependency larger than the thing it validates.
 *
 * This is a trust boundary: the payload comes off the network and is decoded
 * with a codec that is deliberately not authenticated. Never assume the shape.
 */
export function validatePuzzle(value: unknown, expectedDate?: string): Puzzle {
  const bad = (reason: string): never => {
    throw new PuzzleInvalid(reason);
  };

  if (typeof value !== 'object' || value === null) return bad('not an object');
  const p = value as Record<string, unknown>;

  if (p['schemaVersion'] !== SCHEMA_VERSION) {
    return bad(`schemaVersion ${String(p['schemaVersion'])}, expected ${SCHEMA_VERSION}`);
  }
  if (typeof p['id'] !== 'number' || !Number.isInteger(p['id']) || p['id'] < 1) {
    return bad('id must be a positive integer');
  }
  if (typeof p['date'] !== 'string') return bad('date must be a string');
  if (typeof p['start'] !== 'string' || typeof p['end'] !== 'string') {
    return bad('start and end must be strings');
  }

  const isWordList = (v: unknown): v is string[] =>
    Array.isArray(v) && v.every((w) => typeof w === 'string');

  if (!isWordList(p['solution']) || p['solution'].length !== CHAIN_LENGTH) {
    return bad(`solution must be ${CHAIN_LENGTH} words`);
  }
  if (!isWordList(p['bank'])) return bad('bank must be a list of words');

  const bank = p['bank'];
  if (bank.length < BANK_MIN || bank.length > BANK_MAX) {
    return bad(`bank has ${bank.length} tiles, expected ${BANK_MIN}..${BANK_MAX}`);
  }

  // A duplicate would make two tiles indistinguishable and break the
  // word-is-the-tile-id assumption the whole UI rests on (planning.md 3.1.1).
  const unique = new Set(bank);
  if (unique.size !== bank.length) return bad('bank contains duplicate words');

  const solution = p['solution'];
  const missing = solution.filter((w) => !unique.has(w));
  if (missing.length > 0) return bad(`solution words absent from bank: ${missing.join(', ')}`);

  // A drift between id and date would show the wrong puzzle number in every
  // share, which is the one error nobody would notice until it was everywhere.
  const scheduled = dateForPuzzleNumber(p['id']);
  if (p['date'] !== scheduled) {
    return bad(`id ${p['id']} implies ${scheduled} but date says ${p['date']}`);
  }
  if (expectedDate !== undefined && p['date'] !== expectedDate) {
    return bad(`served as ${expectedDate} but claims ${p['date']}`);
  }

  return {
    schemaVersion: SCHEMA_VERSION,
    id: p['id'],
    date: p['date'],
    start: p['start'],
    end: p['end'],
    solution,
    bank,
  };
}

export class HttpPuzzleRepository implements PuzzleRepository {
  constructor(private readonly baseUrl: string) {}

  async load(id: number, date: string): Promise<Puzzle> {
    const res = await fetch(`${this.baseUrl}puzzles/${date}.json`);

    // 404 means the puzzle does not exist — a different state from the network
    // being down, and the two want different screens (planning.md 8.7).
    if (res.status === 404) throw new PuzzleNotFound(date);
    if (!res.ok) throw new Error(`Failed to load puzzle ${id}: HTTP ${res.status}`);

    const envelope = (await res.json()) as unknown;
    if (typeof envelope !== 'object' || envelope === null) {
      throw new PuzzleInvalid('envelope is not an object');
    }
    const { d } = envelope as { d?: unknown };
    if (typeof d !== 'string') throw new PuzzleInvalid('envelope has no payload');

    return validatePuzzle(decode(d, date), date);
  }
}
