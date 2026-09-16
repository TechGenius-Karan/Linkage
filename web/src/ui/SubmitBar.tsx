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
import { HintIcon } from './icons';
import { ShareModal } from './ShareModal';

export interface SubmitBarProps {
  /** Correct count from the most recent attempt, if any. */
  lastCorrect: number | null;
  status: 'playing' | 'won';
  attemptsTaken: number;
  canSubmit: boolean;
  onSubmit: () => void;
  /** 2, 1 or 0 -- badged on the hint button (planning.md 2.5.3). */
  hintsRemaining: number;
  /** Undefined disables the button -- exhausted, or the game is over. */
  onHint: (() => void) | undefined;
  /** Set once the game is won (planning.md 2.7). Opens the share card modal. */
  shareText?: string | undefined;
  /** Same content as `shareText`, split for the card's two-line layout. */
  shareParts?: ShareParts | undefined;
}

/** Left of Check, not in the header -- a hint is an alternative to checking,
 * not app chrome, so it belongs beside the action it substitutes for. The
 * badge always shows the live count, including 0, so "how many are left" and
 * "why is this greyed out" are answered by the same number.
 *
 * No box: just the icon and the badge, same weight as the header's own icon
 * buttons rather than competing with Check as a second filled button. Badge
 * text is a fixed dark colour rather than `text-ink` -- `--ink` and `--moon`
 * both flip toward light in dark mode, which put near-white text on a pale
 * gold badge (illegible). `--moon` never goes dark in either theme, so a
 * fixed dark foreground reads correctly in both. */
function HintButton({
  hintsRemaining,
  onHint,
}: {
  hintsRemaining: number;
  onHint: (() => void) | undefined;
}) {
  const disabled = onHint === undefined;
  return (
    <button
      type="button"
      className={`ring-focus relative grid h-11 w-11 flex-none translate-x-[-15px] translate-y-[2px] place-items-center rounded-lg transition-colors ${
        disabled ? 'cursor-default text-ink-muted opacity-50' : 'text-ink hover:text-accent'
      }`}
      aria-label={`Hint, ${hintsRemaining} left`}
      disabled={disabled}
      onClick={onHint}
    >
      <HintIcon size={28} />
      <span
        aria-hidden="true"
        className="absolute -right-0.5 -top-0.5 grid h-4 w-4 place-items-center rounded-full bg-moon text-[9px] font-bold text-[#1f1d1a]"
      >
        {hintsRemaining}
      </span>
    </button>
  );
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
  hintsRemaining,
  onHint,
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
    <div className="flex flex-col gap-3">
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
        // Check itself must be centered on the row, not the [Hint, Check]
        // pair -- centering the pair (justify-center with just the two
        // buttons) still left Check's own center offset right by half of
        // Hint's width. A spacer matching Hint's width on the other side
        // makes the row symmetric around Check, which is what actually
        // centers Check itself using nothing but flexbox.
        <div className="flex items-center justify-center gap-2.5">
          <HintButton hintsRemaining={hintsRemaining} onHint={onHint} />
          <button
            type="button"
            className={`ring-focus min-h-12 w-24 rounded-lg py-3.5 text-[15px] font-semibold ${
              canSubmit ? 'bg-accent text-ground' : 'cursor-default bg-rule text-ink-muted'
            }`}
            disabled={!canSubmit}
            onClick={onSubmit}
          >
            Check
          </button>
          <div className="w-11 flex-none" aria-hidden="true" />
        </div>
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
