/**
 * Persistence must never break the game (planning.md 2.8).
 *
 * Safari private mode throws on write, storage can be disabled outright, and
 * quota errors are real. Each case here is a player who should still be able
 * to play, not a player who sees a blank page.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { LocalStorageProgressStore, emptyStats } from '../src/data/localStorageProgressStore';
import { MAX_ATTEMPTS, type GameState } from '../src/engine/types';

const state = (puzzleId: number): GameState => ({
  puzzleId,
  slots: [null, null, null, null],
  attempts: [],
  status: 'playing',
  selectedTile: null,
});

/** A minimal in-memory Storage, so tests do not need a browser. */
function installStorage(): Map<string, string> {
  const map = new Map<string, string>();
  vi.stubGlobal('localStorage', {
    getItem: (k: string) => map.get(k) ?? null,
    setItem: (k: string, v: string) => void map.set(k, v),
    removeItem: (k: string) => void map.delete(k),
    key: (i: number) => [...map.keys()][i] ?? null,
    get length() {
      return map.size;
    },
  });
  return map;
}

beforeEach(() => installStorage());
afterEach(() => vi.unstubAllGlobals());

describe('LocalStorageProgressStore', () => {
  it('round-trips progress', () => {
    const store = new LocalStorageProgressStore();
    store.writeProgress(7, state(7));
    expect(store.readProgress(7)).toEqual(state(7));
  });

  it('returns null for a puzzle it has never seen', () => {
    expect(new LocalStorageProgressStore().readProgress(99)).toBeNull();
  });

  it('returns a fresh game rather than throwing on corrupt JSON', () => {
    const map = installStorage();
    map.set('linkage:v1:progress:3', '{ this is not json');
    expect(new LocalStorageProgressStore().readProgress(3)).toBeNull();
  });

  it('rejects well-formed JSON of the wrong shape', () => {
    const map = installStorage();
    map.set('linkage:v1:progress:3', '{"puzzleId":"three"}');
    expect(new LocalStorageProgressStore().readProgress(3)).toBeNull();
  });

  it('rejects an unknown status', () => {
    const map = installStorage();
    map.set(
      'linkage:v1:progress:3',
      JSON.stringify({ ...state(3), status: 'cheating' }),
    );
    expect(new LocalStorageProgressStore().readProgress(3)).toBeNull();
  });

  it('starts from empty stats when nothing is stored', () => {
    expect(new LocalStorageProgressStore().readStats()).toEqual(emptyStats());
    expect(emptyStats().distribution).toHaveLength(MAX_ATTEMPTS);
  });

  it('repairs a distribution of the wrong length', () => {
    // MAX_ATTEMPTS is provisional (planning.md 2.5.1), so a stored histogram
    // from an earlier build will be the wrong size for a returning player.
    const map = installStorage();
    map.set(
      'linkage:v1:stats',
      JSON.stringify({ ...emptyStats(), distribution: [4, 2, 1] }),
    );
    const stats = new LocalStorageProgressStore().readStats();
    expect(stats.distribution).toHaveLength(MAX_ATTEMPTS);
    expect(stats.distribution.slice(0, 3)).toEqual([4, 2, 1]);
  });

  it('prunes progress more than a week older than the newest', () => {
    const map = installStorage();
    for (const id of [1, 5, 12, 13]) map.set(`linkage:v1:progress:${id}`, JSON.stringify(state(id)));
    new LocalStorageProgressStore();
    expect(map.has('linkage:v1:progress:1')).toBe(false);
    expect(map.has('linkage:v1:progress:5')).toBe(false);
    expect(map.has('linkage:v1:progress:12')).toBe(true);
    expect(map.has('linkage:v1:progress:13')).toBe(true);
  });

  it('keeps working when writes throw, as in Safari private mode', () => {
    vi.stubGlobal('localStorage', {
      getItem: () => null,
      setItem: () => {
        throw new DOMException('QuotaExceededError');
      },
      removeItem: () => undefined,
      key: () => null,
      length: 0,
    });
    const store = new LocalStorageProgressStore();
    expect(() => store.writeProgress(1, state(1))).not.toThrow();
    expect(store.persistent).toBe(false);
    // The session still has to work, so the write lands in memory.
    expect(store.readProgress(1)).toEqual(state(1));
  });

  it('keeps working when storage is unavailable entirely', () => {
    vi.stubGlobal('localStorage', {
      get length(): number {
        throw new DOMException('SecurityError');
      },
      getItem: () => {
        throw new DOMException('SecurityError');
      },
      setItem: () => {
        throw new DOMException('SecurityError');
      },
      removeItem: () => undefined,
      key: () => null,
    });
    const store = new LocalStorageProgressStore();
    expect(() => store.writeStats(emptyStats())).not.toThrow();
    expect(store.readStats()).toEqual(emptyStats());
  });
});
