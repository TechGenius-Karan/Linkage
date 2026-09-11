/**
 * The review queue (docs/admin.md 9, 10.3).
 *
 * Five candidates at a time, not one. The first version showed one — right for
 * round 1, where the risk was skimming; wrong at 867 candidates, where a
 * verdict takes two seconds and re-orienting to a fresh screen takes longer
 * than the judgement did.
 *
 * Five needs no client-side bookkeeping, which is the only reason it is
 * affordable. The queue is sorted deterministically, so "the first five
 * pending" after a verdict is *by construction* the four survivors in their
 * original order plus one new arrival. Refetch, render, done — there is no list
 * to reconcile and no way for the two to drift.
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

  if (load.kind === 'loading') return <p className="text-ink-muted">Loading the queue…</p>;

  if (load.kind === 'error') {
    return (
      <div className="flex flex-col gap-3">
        <p className="text-[15px] text-heart">{load.message}</p>
        <pre className="overflow-x-auto rounded-lg border border-rule bg-surface p-3 font-data text-xs">
          cd engine{'\n'}python -m linkage_engine admin
        </pre>
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
    <div className="flex flex-col gap-4">
      <Progress decided={counts.decided} total={counts.total} />

      {error !== null && (
        <p className="rounded-lg border border-heart bg-heart/10 px-3 py-2 text-[13px] text-heart">
          {error}
        </p>
      )}

      {lastDecided !== null && (
        <div className="flex items-center justify-between gap-3 rounded-lg border border-rule bg-surface px-3 py-1.5 text-[13px]">
          <span className="text-ink-muted">{lastDecided.label}</span>
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              const hash = lastDecided.hash;
              setLastDecided(null);
              void act(() => undoPuzzle(hash), null);
            }}
            className="ring-focus rounded px-2 py-1 font-medium underline disabled:opacity-40"
          >
            Undo
          </button>
        </div>
      )}

      {returned.length > 0 && (
        <section className="flex flex-col gap-2">
          <h2 className="text-sm font-semibold">
            Sent back for another look ({returned.length})
          </h2>
          {returned.map((puzzle) => card(puzzle, true))}
        </section>
      )}

      <section className="flex flex-col gap-2">
        <h2 className="text-sm font-semibold">
          Queue{' '}
          <span className="font-data text-xs font-normal text-ink-muted">
            {counts.pending} pending
          </span>
        </h2>
        {puzzles.length === 0 ? (
          <p className="py-8 text-center text-[15px] text-ink-muted">
            Nothing left to review. Run <code className="font-data">linkage generate</code> for
            more.
          </p>
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
    <div className="flex items-center gap-3">
      <span className="h-[3px] flex-1 overflow-hidden rounded-full bg-rule">
        <span className="block h-full rounded-full bg-accent" style={{ width: `${pct}%` }} />
      </span>
      <span className="font-data text-[10px] text-ink-muted">
        {decided} / {total} decided
      </span>
    </div>
  );
}
