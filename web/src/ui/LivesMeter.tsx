/**
 * Presentation tier. Lives as hearts, never as a counter (planning.md 2.5.1).
 *
 * The reframe is the whole point: "3 of 5 attempts used" reads as a budget to
 * spend, hearts read as stakes. Spent hearts stay visible but drained — an
 * outline reads as "empty", a drained fill reads as "spent", and spent is the
 * feeling being aimed at.
 */

import { MAX_ATTEMPTS } from '../engine/types';

export interface LivesMeterProps {
  remaining: number;
}

export function LivesMeter({ remaining }: LivesMeterProps) {
  return (
    <div
      className="flex gap-1.5 text-base leading-none"
      // Never a bare glyph — the count is stated for screen readers
      // (planning.md 8.6).
      aria-label={`${remaining} of ${MAX_ATTEMPTS} lives remaining`}
      role="img"
    >
      {Array.from({ length: MAX_ATTEMPTS }, (_, i) => (
        <span key={i} aria-hidden="true" className={i < remaining ? 'text-heart' : 'text-rule'}>
          &#9829;
        </span>
      ))}
    </div>
  );
}
