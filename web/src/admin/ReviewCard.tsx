/**
 * One candidate, judged (docs/admin.md 2, 10).
 *
 * Compact enough that five fit on screen. The ladder runs sideways with its
 * weakest rung drawn loudest, because 45 verdicts in, `badLink` says that is
 * where reviewers reject — 13 of 14 rejections named a rung in the opening
 * half, and 7 of those named link 1 alone.
 *
 * Approve and Reject are separate outcomes and always will be. A sibling
 * project merged "fix this" into "reject" once and lost puzzles to it — which
 * is also why editing is its own panel rather than a kind of rejection.
 */

import { useState } from 'react';
import type { EditResponse, ManualEdge, QueuePuzzle, WordEdit } from './adminClient';
import { Ladder } from './Ladder';
import { PuzzleEditor } from './PuzzleEditor';

export interface ReviewCardProps {
  puzzle: QueuePuzzle;
  busy: boolean;
  /** Shown on a card that was approved and pulled back (docs/admin.md 12.1). */
  returned?: boolean;
  onApprove: (edits: WordEdit[], edges: ManualEdge[]) => void;
  onReject: (reason: string, badLink: number | null) => void;
}

export function ReviewCard({
  puzzle,
  busy,
  returned = false,
  onApprove,
  onReject,
}: ReviewCardProps) {
  const [reason, setReason] = useState('');
  const [badLink, setBadLink] = useState<number | null>(null);
  const [editing, setEditing] = useState(false);
  const [edits, setEdits] = useState<WordEdit[]>(puzzle.bankEdits);
  const [edges, setEdges] = useState<ManualEdge[]>(puzzle.manualEdges);
  const [state, setState] = useState<EditResponse | null>(null);

  const canReject = reason.trim().length > 0;
  const blocked = (state?.refusals.length ?? 0) > 0;
  const chain = state?.chain ?? puzzle.chain;

  return (
    <article
      className={`flex flex-col gap-2.5 rounded-xl border bg-surface p-4 ${
        returned ? 'border-accent' : 'border-rule'
      }`}
    >
      <header className="flex items-baseline justify-between gap-3">
        <h3 className="font-word text-[15px] font-semibold">
          {chain[0]?.toUpperCase()} → {chain[chain.length - 1]?.toUpperCase()}
        </h3>
        <span className="font-data text-[10px] text-ink-muted">
          {puzzle.quality === null ? '' : `q ${puzzle.quality.toFixed(2)} · `}
          {puzzle.hash.slice(0, 8)}
        </span>
      </header>

      <Ladder
        chain={chain}
        weights={puzzle.linkWeights}
        relations={puzzle.relations}
        asserted={state?.assertedLinks ?? []}
        badLink={badLink}
        onMarkLink={(i) => setBadLink(badLink === i ? null : i)}
        edits={edits}
      />

      {!editing && (
        <div className="flex flex-wrap gap-1">
          {(state?.decoys ?? puzzle.decoys).map((word) => (
            <span
              key={word}
              className="rounded border border-rule px-1.5 py-0.5 font-word text-[13px]"
            >
              {word}
            </span>
          ))}
        </div>
      )}

      {editing && (
        <PuzzleEditor
          puzzle={puzzle}
          edits={edits}
          edges={edges}
          state={state}
          disabled={busy}
          onChange={(nextEdits, nextEdges, nextState) => {
            setEdits(nextEdits);
            setEdges(nextEdges);
            setState(nextState);
          }}
        />
      )}

      <div className="flex flex-wrap items-center gap-2 border-t border-rule pt-2.5">
        <button
          type="button"
          onClick={() => onApprove(edits, edges)}
          disabled={busy || blocked}
          title={blocked ? 'Resolve the refusal first' : undefined}
          className="ring-focus rounded-lg bg-accent px-3 py-1.5 text-[13px] font-semibold text-ground disabled:opacity-40"
        >
          Approve
        </button>
        <button
          type="button"
          onClick={() => onReject(reason.trim(), badLink)}
          disabled={busy || !canReject}
          title={canReject ? undefined : 'A rejection needs a reason'}
          className="ring-focus rounded-lg border border-heart px-3 py-1.5 text-[13px] font-semibold text-heart disabled:opacity-40"
        >
          Reject
        </button>
        <button
          type="button"
          onClick={() => setEditing(!editing)}
          disabled={busy}
          aria-expanded={editing}
          className="ring-focus rounded-lg border border-rule px-3 py-1.5 text-[13px] disabled:opacity-40"
        >
          {editing ? 'Done editing' : 'Edit'}
        </button>
        <input
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Why is this wrong? Required to reject — it is what rebuilds the scorer."
          className="ring-focus min-w-[16rem] flex-1 rounded-lg border border-rule bg-ground px-2.5 py-1.5 text-[13px]"
        />
      </div>

      {badLink !== null && (
        <p className="font-data text-[10px] text-ink-muted">
          link {badLink + 1} blamed · {chain[badLink]} → {chain[badLink + 1]}
        </p>
      )}
    </article>
  );
}
