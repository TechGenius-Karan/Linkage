/**
 * One candidate, judged (docs/admin.md 2, 10).
 *
 * The card used to open with `BOMB → DARK` as a heading and then print the
 * whole chain immediately below, starting with BOMB and ending with DARK. The
 * heading said nothing the next line did not. It is gone, and so are the
 * content hash and the quality score — neither is something a person reads a
 * chain against.
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
  /** Approved once, then pulled back for another look (docs/admin.md 12.1). */
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
    <article className={`adm-card${returned ? ' adm-card--returned' : ''}`}>
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
        <div className="adm-tiles">
          {(state?.decoys ?? puzzle.decoys).map((word) => (
            <span key={word} className="adm-tile">
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

      <div className="adm-actions">
        <button
          type="button"
          className="adm-btn adm-btn--go"
          onClick={() => onApprove(edits, edges)}
          disabled={busy || blocked}
          title={blocked ? 'Resolve the refusal first' : undefined}
        >
          Approve
        </button>
        <button
          type="button"
          className="adm-btn adm-btn--no"
          onClick={() => onReject(reason.trim(), badLink)}
          disabled={busy || !canReject}
          title={canReject ? undefined : 'A rejection needs a reason'}
        >
          Reject
        </button>
        <button
          type="button"
          className="adm-btn"
          onClick={() => setEditing(!editing)}
          disabled={busy}
          aria-expanded={editing}
        >
          {editing ? 'Done' : 'Edit'}
        </button>
        <input
          className="adm-input adm-input--grow"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          aria-label="Why this puzzle fails"
          placeholder={
            badLink === null
              ? 'Why does it fail? Click a link above to say where.'
              : `Why does ${chain[badLink]} → ${chain[badLink + 1]} fail?`
          }
        />
      </div>
    </article>
  );
}
