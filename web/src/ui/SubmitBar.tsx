/**
 * Presentation tier. Lives, feedback, and the Check button (planning.md 8.5).
 *
 * The feedback line is the *entire* channel the player gets: a number, stated
 * in words. That makes it colourblind-safe for free (planning.md 2.5) — colour
 * is never the signal here, and must not become one.
 */

import { CHAIN_LENGTH } from '../engine/types';
import { LivesMeter } from './LivesMeter';

export interface SubmitBarProps {
  livesRemaining: number;
  /** Correct count from the most recent attempt, if any. */
  lastCorrect: number | null;
  status: 'playing' | 'won' | 'lost';
  attemptsTaken: number;
  canSubmit: boolean;
  onSubmit: () => void;
}

function message(
  status: SubmitBarProps['status'],
  lastCorrect: number | null,
  attemptsTaken: number,
): string {
  if (status === 'won') {
    return attemptsTaken === 1 ? 'Solved first try.' : `Solved in ${attemptsTaken}.`;
  }
  if (status === 'lost') return 'Out of lives — here is the chain.';
  if (lastCorrect === null) return 'Fill all four, then check.';
  return `${lastCorrect} of ${CHAIN_LENGTH} correct`;
}

export function SubmitBar({
  livesRemaining,
  lastCorrect,
  status,
  attemptsTaken,
  canSubmit,
  onSubmit,
}: SubmitBarProps) {
  const text = message(status, lastCorrect, attemptsTaken);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between gap-3">
        <LivesMeter remaining={livesRemaining} />
        {/* Announced after each submit, so the result reaches a screen reader
            without it having to hunt for what changed (planning.md 8.6). */}
        <p className="text-[15px] font-medium text-ink-muted" aria-live="polite">
          {text}
          {status === 'playing' && lastCorrect !== null
            ? `. ${livesRemaining} ${livesRemaining === 1 ? 'life' : 'lives'} remaining.`
            : ''}
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
    </div>
  );
}
