/**
 * Presentation tier. The feedback line and the Check button (planning.md 8.5).
 *
 * The feedback line is the *entire* channel the player gets: a number, stated
 * in words. That makes it colourblind-safe for free (planning.md 2.5) — colour
 * is never the signal here, and must not become one.
 *
 * A win is announced by the share panel opening itself, not by this line —
 * see the effect below.
 */

import { useEffect, useState } from 'react';
import type { ShareParts } from '../engine/shareText';
import { CHAIN_LENGTH } from '../engine/types';
import { ShareModal } from './ShareModal';

export interface SubmitBarProps {
  /** Correct count from the most recent attempt, if any. */
  lastCorrect: number | null;
  status: 'playing' | 'won';
  attemptsTaken: number;
  canSubmit: boolean;
  onSubmit: () => void;
  /** Set once the game is won (planning.md 2.7). Opens the share card modal. */
  shareText?: string | undefined;
  /** Same content as `shareText`, split for the card's two-line layout. */
  shareParts?: ShareParts | undefined;
}

/** Tiered by attempts taken, so a first-try solve reads differently from a
 * hard-won one — same spirit as Connections' Perfect/Solid/Phew ladder. */
const CELEBRATIONS = ['🎉 Perfect!', '✨ Nicely done!', '👏 Solved it!', '🙌 Got there!'];

function celebrationFor(attemptsTaken: number): string {
  return CELEBRATIONS[Math.min(attemptsTaken, CELEBRATIONS.length) - 1]!;
}

function message(lastCorrect: number | null): string {
  if (lastCorrect === null) return 'Fill all four, then check.';
  return `${lastCorrect} of ${CHAIN_LENGTH} correct`;
}

export function SubmitBar({
  lastCorrect,
  status,
  attemptsTaken,
  canSubmit,
  onSubmit,
  shareText,
  shareParts,
}: SubmitBarProps) {
  const [shareOpen, setShareOpen] = useState(false);

  // The win panel is the win screen -- it opens itself the moment the game is
  // won, rather than waiting for the player to find a "Share result" button.
  useEffect(() => {
    if (status === 'won') setShareOpen(true);
  }, [status]);

  return (
    <div className="flex flex-col gap-6">
      {status === 'playing' && (
        // Announced after each submit, so the result reaches a screen reader
        // without it having to hunt for what changed (planning.md 8.6). Keyed
        // on the attempt count so the fade-in retriggers on every check.
        <p
          key={attemptsTaken}
          className="animate-feedback-in rounded-full bg-ground px-4 py-2.5 text-center text-[15px] font-medium text-ink-muted"
          aria-live="polite"
        >
          {message(lastCorrect)}
        </p>
      )}

      {status === 'playing' && (
        <button
          type="button"
          className={`ring-focus min-h-12 rounded-lg py-3.5 text-[15px] font-semibold ${
            canSubmit ? 'bg-accent text-ground' : 'cursor-default bg-rule text-ink-muted'
          }`}
          disabled={!canSubmit}
          onClick={onSubmit}
        >
          Check
        </button>
      )}

      {status === 'won' && shareText !== undefined && shareParts !== undefined && (
        <>
          <button
            type="button"
            className="ring-focus min-h-12 rounded-lg bg-accent py-3.5 text-[15px] font-semibold text-ground"
            onClick={() => setShareOpen(true)}
          >
            Share result
          </button>
          <ShareModal
            open={shareOpen}
            onClose={() => setShareOpen(false)}
            shareText={shareText}
            shareParts={shareParts}
            celebration={celebrationFor(attemptsTaken)}
          />
        </>
      )}
    </div>
  );
}
