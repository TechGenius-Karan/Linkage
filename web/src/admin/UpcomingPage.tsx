/**
 * What is shipping, in date order (docs/admin.md 12.3).
 *
 * A separate screen rather than a section on the pool, because "what goes out
 * over the next month" is a different question from "what should I schedule
 * next", asked at a different time and usually answered by just reading.
 *
 * One action: **return to pool**, which is `unschedule` — already distinct from
 * unapproving, because the reviewer still likes the puzzle and only wants a
 * different day for it.
 *
 * No new endpoint: `pool` already returns everything dated.
 */

import { useCallback, useEffect, useState } from 'react';
import { fetchPool, unschedulePuzzle, type PoolResponse } from './adminClient';
import { Ladder } from './Ladder';

type Load =
  | { kind: 'loading' }
  | { kind: 'ready'; data: PoolResponse }
  | { kind: 'error'; message: string };

export interface UpcomingPageProps {
  onChanged: () => void;
}

export function UpcomingPage({ onChanged }: UpcomingPageProps) {
  const [load, setLoad] = useState<Load>({ kind: 'loading' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setLoad({ kind: 'ready', data: await fetchPool() });
    } catch (err) {
      setLoad({ kind: 'error', message: (err as Error).message });
    }
  }, []);

  useEffect(() => void refresh(), [refresh]);

  if (load.kind === 'loading') return <p className="text-ink-muted">Loading the calendar…</p>;
  if (load.kind === 'error') return <p className="text-[15px] text-heart">{load.message}</p>;

  const { scheduled, archive } = load.data;

  const release = async (hash: string) => {
    setBusy(true);
    setError(null);
    try {
      await unschedulePuzzle(hash);
      await refresh();
      onChanged();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <p className="font-data text-[10px] text-ink-muted">
        {archive.count} already shipped
        {archive.lastDate !== null ? ` · through ${archive.lastDate}` : ''} · next slot{' '}
        {archive.nextDate}
      </p>

      {error !== null && (
        <p className="rounded-lg border border-heart bg-heart/10 px-3 py-2 text-[13px] text-heart">
          {error}
        </p>
      )}

      {scheduled.length === 0 ? (
        <p className="py-8 text-center text-[15px] text-ink-muted">
          Nothing on the calendar. Export will propose dates for whatever is in the pool.
        </p>
      ) : (
        <ol className="flex flex-col gap-1.5">
          {scheduled.map((puzzle) => (
            <li
              key={puzzle.hash}
              className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-rule bg-surface px-3 py-2"
            >
              <div className="flex flex-wrap items-center gap-3">
                <time
                  dateTime={puzzle.date ?? undefined}
                  className="font-data text-xs tabular-nums text-ink-muted"
                >
                  {puzzle.date}
                </time>
                <Ladder
                  chain={puzzle.chain}
                  weights={puzzle.linkWeights}
                  relations={puzzle.relations}
                  edits={puzzle.bankEdits}
                />
              </div>
              <div className="flex shrink-0 items-center gap-2">
                {puzzle.manualEdges.length > 0 && (
                  <span
                    title="Ships a link the reviewer asserted, not ConceptNet"
                    className="font-data text-[10px] text-accent"
                  >
                    {puzzle.manualEdges.length} asserted
                  </span>
                )}
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void release(puzzle.hash)}
                  title="Off the calendar, back to the approved pool"
                  className="ring-focus rounded-md px-2 py-1 text-xs underline disabled:opacity-40"
                >
                  Return to pool
                </button>
              </div>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
