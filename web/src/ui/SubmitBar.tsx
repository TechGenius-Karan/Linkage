/**
 * Presentation tier. The timer, feedback, and the Check button (planning.md 8.5).
 *
 * The feedback line is the *entire* channel the player gets: a number, stated
 * in words. That makes it colourblind-safe for free (planning.md 2.5) — colour
 * is never the signal here, and must not become one.
 */

import { useState } from 'react';
import { CHAIN_LENGTH } from '../engine/types';
import { Timer } from './Timer';

export interface SubmitBarProps {
  elapsedMs: number;
  hintFlash: boolean;
  /** Correct count from the most recent attempt, if any. */
  lastCorrect: number | null;
  status: 'playing' | 'won';
  attemptsTaken: number;
  canSubmit: boolean;
  onSubmit: () => void;
  /** Set once the game is won (planning.md 2.5.2). Local clipboard copy, no backend. */
  shareText?: string | undefined;
}

function message(
  status: SubmitBarProps['status'],
  lastCorrect: number | null,
  attemptsTaken: number,
): string {
  if (status === 'won') {
    return attemptsTaken === 1 ? 'Solved first try.' : `Solved in ${attemptsTaken}.`;
  }
  if (lastCorrect === null) return 'Fill all four, then check.';
  return `${lastCorrect} of ${CHAIN_LENGTH} correct`;
}

export function SubmitBar({
  elapsedMs,
  hintFlash,
  lastCorrect,
  status,
  attemptsTaken,
  canSubmit,
  onSubmit,
  shareText,
}: SubmitBarProps) {
  const text = message(status, lastCorrect, attemptsTaken);
  const [copied, setCopied] = useState(false);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between gap-3">
        <Timer elapsedMs={elapsedMs} hintFlash={hintFlash} />
        {/* Announced after each submit, so the result reaches a screen reader
            without it having to hunt for what changed (planning.md 8.6). */}
        <p className="text-[15px] font-medium text-ink-muted" aria-live="polite">
          {text}
        </p>
      </div>

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

      {status === 'won' && shareText !== undefined && (
        <button
          type="button"
          className="ring-focus min-h-12 rounded-lg bg-accent py-3.5 text-[15px] font-semibold text-ground"
          onClick={() => {
            navigator.clipboard
              .writeText(shareText)
              .then(() => {
                setCopied(true);
                setTimeout(() => setCopied(false), 1_500);
              })
              // Clipboard access can be denied; the game itself already succeeded.
              .catch(() => undefined);
          }}
        >
          {copied ? 'Copied!' : 'Share result'}
        </button>
      )}
    </div>
  );
}
