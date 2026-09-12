/**
 * The review queue (docs/admin.md 9, 10.3).
 *
 * Five candidates at a time, which needs no client-side bookkeeping: the queue
 * is sorted deterministically, so "the first five pending" after a verdict is
 * by construction the four survivors in their original order plus one new
 * arrival. Refetch and render — no list to reconcile, nothing that can drift.
 */

import { useCallback, useEffect, useState } from 'react';
import {
  approvePuzzle,
  fetchQueue,
  rejectPuzzle,
  undoPuzzle,
  type ManualEdge,
  type QueueCounts,
  type QueuePuzzle,
  type WordEdit,
} from './adminClient';
import { ReviewCard } from './ReviewCard';

type Load =
  | { kind: 'loading' }
  | { kind: 'ready'; puzzles: QueuePuzzle[]; returned: QueuePuzzle[]; counts: QueueCounts }
  | { kind: 'error'; message: string };

export interface ReviewPageProps {
  onCounts: (counts: QueueCounts) => void;
}

export function ReviewPage({ onCounts }: ReviewPageProps) {
  const [load, setLoad] = useState<Load>({ kind: 'loading' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  /** The last verdict, so a misclick is one click from undone. */
  const [lastDecided, setLastDecided] = useState<{ hash: string; label: string } | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await fetchQueue();
      setLoad({ kind: 'ready', ...data });
      onCounts(data.counts);
    } catch (err) {
      setLoad({ kind: 'error', message: (err as Error).message });
    }
  }, [onCounts]);

  useEffect(() => void refresh(), [refresh]);

  const act = async (
    fn: () => Promise<unknown>,
    decided: { hash: string; label: string } | null,
  ) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
      setLastDecided(decided);
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  if (load.kind === 'loading') return <p className="adm-empty">Loading the queue…</p>;

  if (load.kind === 'error') {
    return (
      <div className="adm-panel">
        <p className="adm-refusal">{load.message}</p>
        <p className="adm-note">Start it with:</p>
        <p className="adm-meta">cd engine &nbsp;·&nbsp; python -m linkage_engine admin</p>
      </div>
    );
  }

  const { puzzles, returned, counts } = load;

  const card = (puzzle: QueuePuzzle, isReturned: boolean) => (
    <ReviewCard
      key={puzzle.hash}
      puzzle={puzzle}
      busy={busy}
      returned={isReturned}
      onApprove={(edits: WordEdit[], edges: ManualEdge[]) =>
        void act(() => approvePuzzle(puzzle.hash, edits, edges), {
          hash: puzzle.hash,
          label: `Approved ${puzzle.start} → ${puzzle.end}`,
        })
      }
      onReject={(reason, badLink) =>
        void act(() => rejectPuzzle(puzzle.hash, reason, badLink), {
          hash: puzzle.hash,
          label: `Rejected ${puzzle.start} → ${puzzle.end}`,
        })
      }
    />
  );

  return (
    <div>
      <Progress decided={counts.decided} total={counts.total} />

      {error !== null && <p className="adm-refusal">{error}</p>}

      {lastDecided !== null && (
        <div className="adm-row">
          <span className="adm-note">{lastDecided.label}</span>
          <button
            type="button"
            className="adm-btn adm-btn--quiet"
            disabled={busy}
            onClick={() => {
              const hash = lastDecided.hash;
              setLastDecided(null);
              void act(() => undoPuzzle(hash), null);
            }}
          >
            Undo
          </button>
        </div>
      )}

      {returned.length > 0 && (
        <section>
          <div className="adm-section">
            <h2 className="adm-h2">Sent back</h2>
            <span className="adm-meta">{returned.length}</span>
          </div>
          {returned.map((puzzle) => card(puzzle, true))}
        </section>
      )}

      <section>
        <div className="adm-section">
          <h2 className="adm-h2">Queue</h2>
          <span className="adm-meta">{counts.pending.toLocaleString()} waiting</span>
        </div>
        {puzzles.length === 0 ? (
          <p className="adm-empty">Nothing left to review.</p>
        ) : (
          puzzles.map((puzzle) => card(puzzle, false))
        )}
      </section>
    </div>
  );
}

/**
 * One number: am I getting anywhere.
 *
 * Not a dashboard — docs/admin.md 3 rejected one, because the number that
 * matters is always about *this* puzzle. But "will this ever end" is the
 * question that decides whether a reviewer keeps going, and it has an answer.
 */
function Progress({ decided, total }: { decided: number; total: number }) {
  const pct = total === 0 ? 0 : (decided / total) * 100;
  return (
    <div className="adm-progress">
      <span className="adm-progress-track">
        <span className="adm-progress-fill" style={{ width: `${pct}%` }} />
      </span>
      <span className="adm-meta">
        {decided} of {total.toLocaleString()}
      </span>
    </div>
  );
}
