/**
 * One candidate, judged (planning.md 16.2).
 *
 * The ladder is rendered with its **links between the words**, and each link is
 * a button. That is the whole design: round 1's most useful finding was that a
 * single bad rung ruined otherwise-good chains, and a rung index can be
 * aggregated across a hundred verdicts where free text cannot.
 *
 * Approve and Reject are separate outcomes and always will be. A sibling
 * project merged "fix this" into "reject" once and lost puzzles to it.
 */

import { useState } from 'react';
import type { QueuePuzzle } from './adminClient';

export interface ReviewCardProps {
  puzzle: QueuePuzzle;
  busy: boolean;
  onApprove: () => void;
  onReject: (reason: string, badLink: number | null) => void;
}

export function ReviewCard({ puzzle, busy, onApprove, onReject }: ReviewCardProps) {
  const [reason, setReason] = useState('');
  const [badLink, setBadLink] = useState<number | null>(null);

  const canReject = reason.trim().length > 0;

  return (
    <article className="flex flex-col gap-4 rounded-xl border border-rule bg-surface p-5">
      <header className="flex items-baseline justify-between gap-3">
        <h2 className="font-word text-lg font-semibold">
          {puzzle.start.toUpperCase()} → {puzzle.end.toUpperCase()}
        </h2>
        <span className="text-xs text-ink-muted">
          {puzzle.quality === null ? '' : `quality ${puzzle.quality.toFixed(2)} · `}
          {puzzle.hash.slice(0, 8)}
        </span>
      </header>

      <div className="flex flex-col gap-1">
        <p className="text-xs text-ink-muted">
          Click a link to mark it as the one that fails.
        </p>
        <ol className="flex flex-col">
          {puzzle.chain.map((word, i) => (
            <li key={`${word}-${i}`} className="flex flex-col">
              <span
                className={`font-word text-[17px] ${
                  i === 0 || i === puzzle.chain.length - 1
                    ? 'font-semibold uppercase tracking-wide'
                    : ''
                }`}
              >
                {word}
              </span>
              {i < puzzle.chain.length - 1 && (
                <LinkButton
                  index={i}
                  weight={puzzle.linkWeights[i]}
                  relations={puzzle.relations[i]}
                  selected={badLink === i}
                  from={word}
                  to={puzzle.chain[i + 1] ?? ''}
                  onToggle={() => setBadLink(badLink === i ? null : i)}
                />
              )}
            </li>
          ))}
        </ol>
      </div>

      <div>
        <div className="mb-1.5 text-xs font-medium text-ink-muted">
          Decoys ({puzzle.decoys.length})
        </div>
        <div className="flex flex-wrap gap-1.5">
          {puzzle.decoys.map((word) => (
            <span
              key={word}
              className="rounded-md border border-rule px-2 py-1 font-word text-[13px]"
            >
              {word}
            </span>
          ))}
        </div>
      </div>

      <div className="flex flex-col gap-2 border-t border-rule pt-4">
        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={2}
          placeholder="Why is this wrong? Required to reject — it is what rebuilds the scorer."
          className="ring-focus w-full resize-y rounded-lg border border-rule bg-ground px-3 py-2 text-[13px]"
        />
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={onApprove}
            disabled={busy}
            className="ring-focus rounded-lg bg-accent px-4 py-2 text-[13px] font-semibold text-ground disabled:opacity-40"
          >
            Approve
          </button>
          <button
            type="button"
            onClick={() => onReject(reason.trim(), badLink)}
            disabled={busy || !canReject}
            title={canReject ? undefined : 'A rejection needs a reason'}
            className="ring-focus rounded-lg border border-heart px-4 py-2 text-[13px] font-semibold text-heart disabled:opacity-40"
          >
            Reject
          </button>
          {badLink !== null && (
            <span className="text-xs text-ink-muted">
              link {badLink + 1} marked · {puzzle.chain[badLink]} → {puzzle.chain[badLink + 1]}
            </span>
          )}
        </div>
        <p className="text-xs text-ink-muted">
          Approving records taste. It does not schedule anything.
        </p>
      </div>
    </article>
  );
}

interface LinkButtonProps {
  index: number;
  weight: number | undefined;
  relations: string[] | undefined;
  selected: boolean;
  from: string;
  to: string;
  onToggle: () => void;
}

function LinkButton({
  index,
  weight,
  relations,
  selected,
  from,
  to,
  onToggle,
}: LinkButtonProps) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-pressed={selected}
      aria-label={`Mark link ${index + 1}, ${from} to ${to}, as the weak one`}
      className={`ring-focus my-0.5 flex w-fit items-center gap-2 rounded-md px-2 py-0.5 text-left text-xs ${
        selected ? 'bg-heart/15 text-heart' : 'text-ink-muted hover:bg-accent-sub'
      }`}
    >
      <span aria-hidden="true">↓</span>
      <span>{weight === undefined ? '—' : weight.toFixed(1)}</span>
      {relations !== undefined && relations.length > 0 && (
        <span className="opacity-70">{relations.join('/')}</span>
      )}
    </button>
  );
}
