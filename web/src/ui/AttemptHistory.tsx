/**
 * Presentation tier. Spent attempts as counts (planning.md 8.5).
 *
 * Counts only — never which slots were right. Showing the tiles from a past
 * attempt would let a player diff two rows and recover positional information,
 * which is exactly what the feedback model withholds (planning.md 2.5).
 */

import { CHAIN_LENGTH, type Attempt } from '../engine/types';

export interface AttemptHistoryProps {
  attempts: Attempt[];
}

export function AttemptHistory({ attempts }: AttemptHistoryProps) {
  if (attempts.length === 0) return null;

  return (
    <ol className="flex flex-col gap-1.5 text-[13px] text-ink-muted">
      {attempts.map((attempt, i) => (
        <li key={i} className="flex justify-between border-t border-rule pt-1.5">
          <span>Attempt {i + 1}</span>
          <span>
            {attempt.correctCount} of {CHAIN_LENGTH}
          </span>
        </li>
      ))}
    </ol>
  );
}
