/**
 * The share card (planning.md 2.5.2, 2.5.3) — net new. No backend, no
 * cross-player comparison: just the puzzle number, the time, and whether a
 * hint was used, formatted as plain text for a share sheet or clipboard.
 */

import { describe, expect, it } from 'vitest';
import { buildShareParts, buildShareText } from '../src/engine/shareText';
import type { GameState } from '../src/engine/types';

const NOW = 1_700_000_000_000;

/** `totalMs` is what `elapsedMs()` should report once hint penalties are folded in. */
const won = (totalMs: number, hintsUsed: string[] = []): GameState => {
  const hintPenaltyMs = hintsUsed.length * 20_000;
  return {
    puzzleId: 42,
    slots: ['ocean', 'blue', 'sky', 'birds'],
    attempts: [{ tiles: ['ocean', 'blue', 'sky', 'birds'], correctCount: 4 }],
    status: 'won',
    selectedTile: null,
    hintsUsed,
    startedAt: NOW,
    pausedAt: null,
    totalPausedMs: 0,
    hintPenaltyMs,
    finishedAt: NOW + (totalMs - hintPenaltyMs),
  };
};

describe('buildShareText', () => {
  it('states the puzzle number and time as mm:ss', () => {
    expect(buildShareText(won(107_000))).toBe('Linkage #42 — solved in 1:47\nhttps://linkage-daily.netlify.app');
  });

  it('pads seconds under ten', () => {
    expect(buildShareText(won(65_000))).toBe('Linkage #42 — solved in 1:05\nhttps://linkage-daily.netlify.app');
  });

  it('handles a sub-minute solve', () => {
    expect(buildShareText(won(9_000))).toBe('Linkage #42 — solved in 0:09\nhttps://linkage-daily.netlify.app');
  });

  it('says nothing about hints when none were used', () => {
    expect(buildShareText(won(30_000))).not.toContain('hint');
  });

  it('notes a single hint in the singular', () => {
    expect(buildShareText(won(50_000, ['blue']))).toBe(
      'Linkage #42 — solved in 0:50 (1 hint used)\nhttps://linkage-daily.netlify.app',
    );
  });

  it('notes multiple hints in the plural', () => {
    expect(buildShareText(won(90_000, ['blue', 'birds']))).toBe(
      'Linkage #42 — solved in 1:30 (2 hints used)\nhttps://linkage-daily.netlify.app',
    );
  });

  it('always appends the site link', () => {
    expect(buildShareText(won(30_000))).toContain('https://linkage-daily.netlify.app');
  });
});

describe('buildShareParts', () => {
  it('never includes the site link — only buildShareText does', () => {
    const { headline, hintNote } = buildShareParts(won(50_000, ['blue']));
    expect(headline).not.toContain('http');
    expect(hintNote).not.toContain('http');
  });
});
