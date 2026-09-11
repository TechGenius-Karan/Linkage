/**
 * The review queue (planning.md 16).
 *
 * One puzzle at a time rather than a scrolling list. Round 1 was 25 candidates
 * judged in one sitting, and a wall of cards invites skimming — which is the
 * failure mode a human review gate exists to prevent.
 */

import { useCallback, useEffect, useState } from 'react';
import {
  approvePuzzle,
  fetchQueue,
  rejectPuzzle,
  undoPuzzle,
  type BankEdit,
  type QueueCounts,
  type QueuePuzzle,
} from './adminClient';
import { PoolPage } from './PoolPage';
import { ReviewCard } from './ReviewCard';

type Load =
  | { kind: 'loading' }
  | { kind: 'ready'; puzzles: QueuePuzzle[]; counts: QueueCounts }
  | { kind: 'error'; message: string };

/** Two screens. A router for two screens would be a dependency earning nothing. */
type View = 'queue' | 'pool';

export function AdminApp() {
  const [view, setView] = useState<View>('queue');
  const [load, setLoad] = useState<Load>({ kind: 'loading' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  /** The last verdict, so a misclick is one click from undone. */
  const [lastDecided, setLastDecided] = useState<{ hash: string; label: string } | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await fetchQueue();
      setLoad({ kind: 'ready', puzzles: data.puzzles, counts: data.counts });
    } catch (err) {
      setLoad({ kind: 'error', message: (err as Error).message });
    }
  }, []);

  useEffect(() => void refresh(), [refresh]);

  const act = async (fn: () => Promise<unknown>, decided: { hash: string; label: string } | null) => {
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

  if (load.kind === 'loading') {
    return (
      <Shell view={view} onView={setView}>
        <p className="text-ink-muted">Loading the queue…</p>
      </Shell>
    );
  }

  if (load.kind === 'error') {
    return (
      <Shell view={view} onView={setView}>
        <p className="text-[15px] text-heart">{load.message}</p>
        <pre className="overflow-x-auto rounded-lg border border-rule bg-surface p-3 text-xs">
          cd engine{'\n'}python -m linkage_engine admin
        </pre>
      </Shell>
    );
  }

  const current = load.puzzles[0];

  return (
    <Shell counts={load.counts} view={view} onView={setView}>
      {view === 'pool' && <PoolPage onChanged={() => void refresh()} />}
      {view === 'queue' && (
        <>
      {error !== null && (
        <p className="rounded-lg border border-heart bg-heart/10 px-3 py-2 text-[13px] text-heart">
          {error}
        </p>
      )}

      {lastDecided !== null && (
        <div className="flex items-center justify-between gap-3 rounded-lg border border-rule bg-surface px-3 py-2 text-[13px]">
          <span className="text-ink-muted">{lastDecided.label}</span>
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              const hash = lastDecided.hash;
              setLastDecided(null);
              void act(() => undoPuzzle(hash), null);
            }}
            className="ring-focus rounded-md px-2 py-1 font-medium underline disabled:opacity-40"
          >
            Undo
          </button>
        </div>
      )}

      {current === undefined ? (
        <p className="py-12 text-center text-[15px] text-ink-muted">
          Nothing left to review. Run <code>linkage generate</code> for more.
        </p>
      ) : (
        <ReviewCard
          key={current.hash}
          puzzle={current}
          busy={busy}
          onApprove={(edits: BankEdit[]) =>
            void act(() => approvePuzzle(current.hash, edits), {
              hash: current.hash,
              label: `Approved ${current.start} → ${current.end}`,
            })
          }
          onReject={(reason, badLink) =>
            void act(() => rejectPuzzle(current.hash, reason, badLink), {
              hash: current.hash,
              label: `Rejected ${current.start} → ${current.end}`,
            })
          }
        />
      )}
        </>
      )}
    </Shell>
  );
}

function Shell({
  children,
  counts,
  view,
  onView,
}: {
  children: React.ReactNode;
  counts?: QueueCounts;
  view: View;
  onView: (view: View) => void;
}) {
  return (
    <div className="flex min-h-screen justify-center px-4 py-8">
      <div className="flex w-full max-w-xl flex-col gap-5">
        <header className="flex items-baseline justify-between gap-3">
          <h1 className="font-word text-xl font-semibold">Linkage review</h1>
          {counts !== undefined && (
            <span className="text-xs text-ink-muted">
              {counts.pending} pending · {counts.approved} approved · {counts.scheduled} scheduled ·{' '}
              {counts.rejected} rejected
            </span>
          )}
        </header>
        <nav className="flex gap-1 border-b border-rule">
          {(['queue', 'pool'] as const).map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => onView(tab)}
              aria-current={view === tab ? 'page' : undefined}
              className={`ring-focus -mb-px rounded-t-md border-b-2 px-3 py-1.5 text-[13px] capitalize ${
                view === tab
                  ? 'border-accent font-semibold text-accent'
                  : 'border-transparent text-ink-muted hover:text-ink'
              }`}
            >
              {tab}
            </button>
          ))}
        </nav>
        {children}
      </div>
    </div>
  );
}
