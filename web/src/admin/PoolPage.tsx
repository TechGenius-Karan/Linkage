/**
 * The approved pool, and choosing a date (planning.md 16.2, 16.6).
 *
 * Approving records taste; scheduling is a separate act. This is the screen
 * where the second one happens, and the whole reason the decision record
 * carries `date: null` until somebody deliberately fills it in.
 *
 * Dates are offered as a **run of slots**, not a date picker. The archive's one
 * hard invariant is `date == epoch + (id - 1)` days, so a puzzle occupies a day
 * in an unbroken sequence — a free-form picker would let a reviewer punch a
 * hole that export could never fill.
 */

import { useCallback, useEffect, useState } from 'react';
import {
  fetchPool,
  schedulePuzzle,
  unschedulePuzzle,
  type PoolPuzzle,
  type PoolResponse,
} from './adminClient';

type Load =
  | { kind: 'loading' }
  | { kind: 'ready'; data: PoolResponse }
  | { kind: 'error'; message: string };

export interface PoolPageProps {
  /** Refresh the queue counts in the header, which a schedule changes. */
  onChanged: () => void;
}

export function PoolPage({ onChanged }: PoolPageProps) {
  const [load, setLoad] = useState<Load>({ kind: 'loading' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [picking, setPicking] = useState<string | null>(null);
  /** Corpus warnings from the last schedule — 16.6's whole point. */
  const [warnings, setWarnings] = useState<{ date: string; lines: string[] } | null>(null);

  const refresh = useCallback(async () => {
    try {
      setLoad({ kind: 'ready', data: await fetchPool() });
    } catch (err) {
      setLoad({ kind: 'error', message: (err as Error).message });
    }
  }, []);

  useEffect(() => void refresh(), [refresh]);

  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
      await refresh();
      onChanged();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  if (load.kind === 'loading') return <p className="text-ink-muted">Loading the pool…</p>;
  if (load.kind === 'error') return <p className="text-[15px] text-heart">{load.message}</p>;

  const { scheduled, pooled, slots, archive } = load.data;
  const free = slots.filter((slot) => slot.hash === null);

  return (
    <div className="flex flex-col gap-5">
      <p className="text-xs text-ink-muted">
        {archive.count} shipped
        {archive.lastDate !== null ? `, through ${archive.lastDate}` : ''} · next slot{' '}
        {archive.nextDate}
      </p>

      {error !== null && (
        <p className="rounded-lg border border-heart bg-heart/10 px-3 py-2 text-[13px] text-heart">
          {error}
        </p>
      )}

      {warnings !== null && (
        <div className="rounded-lg border border-rule bg-surface px-3 py-2 text-[13px]">
          <div className="flex items-baseline justify-between gap-3">
            <span className="font-medium">Scheduled for {warnings.date}</span>
            <button
              type="button"
              onClick={() => setWarnings(null)}
              className="ring-focus rounded-md px-1.5 text-xs underline"
            >
              Dismiss
            </button>
          </div>
          {warnings.lines.length === 0 ? (
            <p className="mt-1 text-xs text-ink-muted">No corpus warnings on that day.</p>
          ) : (
            <ul className="mt-1 flex flex-col gap-0.5 text-xs text-heart">
              {warnings.lines.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      <section>
        <h2 className="mb-2 text-sm font-semibold">On the calendar ({scheduled.length})</h2>
        {scheduled.length === 0 ? (
          <p className="text-[13px] text-ink-muted">
            Nothing scheduled. Export will propose dates for the pool below.
          </p>
        ) : (
          <ul className="flex flex-col gap-1.5">
            {scheduled.map((puzzle) => (
              <li
                key={puzzle.hash}
                className="flex items-center justify-between gap-3 rounded-lg border border-rule bg-surface px-3 py-2"
              >
                <span className="flex items-baseline gap-2">
                  <span className="text-xs tabular-nums text-ink-muted">{puzzle.date}</span>
                  <Ladder puzzle={puzzle} />
                </span>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void act(() => unschedulePuzzle(puzzle.hash))}
                  className="ring-focus shrink-0 rounded-md px-2 py-1 text-xs underline disabled:opacity-40"
                >
                  Unschedule
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h2 className="mb-2 text-sm font-semibold">Approved, waiting for a date ({pooled.length})</h2>
        {pooled.length === 0 ? (
          <p className="text-[13px] text-ink-muted">
            The pool is empty. Approve some candidates in the queue.
          </p>
        ) : (
          <ul className="flex flex-col gap-1.5">
            {pooled.map((puzzle) => (
              <li
                key={puzzle.hash}
                className="flex flex-col gap-2 rounded-lg border border-rule bg-surface px-3 py-2"
              >
                <div className="flex items-center justify-between gap-3">
                  <Ladder puzzle={puzzle} />
                  <button
                    type="button"
                    disabled={busy || free.length === 0}
                    onClick={() => setPicking(picking === puzzle.hash ? null : puzzle.hash)}
                    aria-expanded={picking === puzzle.hash}
                    title={free.length === 0 ? 'Every slot in the run is taken' : undefined}
                    className="ring-focus shrink-0 rounded-md border border-rule px-2 py-1 text-xs disabled:opacity-40"
                  >
                    Schedule
                  </button>
                </div>
                {picking === puzzle.hash && (
                  <div className="flex flex-wrap gap-1">
                    {free.map((slot) => (
                      <button
                        key={slot.date}
                        type="button"
                        disabled={busy}
                        onClick={() =>
                          void act(async () => {
                            const result = await schedulePuzzle(puzzle.hash, slot.date);
                            setWarnings({ date: result.date, lines: result.warnings });
                            setPicking(null);
                          })
                        }
                        className="ring-focus rounded-md border border-rule px-2 py-1 text-xs tabular-nums disabled:opacity-40 hover:bg-accent-sub"
                      >
                        {slot.date.slice(5)}
                      </button>
                    ))}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function Ladder({ puzzle }: { puzzle: PoolPuzzle }) {
  return (
    <span className="font-word text-[13px]">
      <span className="font-semibold uppercase">{puzzle.start}</span>
      <span className="text-ink-muted"> → {puzzle.solution.join(' → ')} → </span>
      <span className="font-semibold uppercase">{puzzle.end}</span>
      {puzzle.bankEdits.length > 0 && (
        <span className="ml-1.5 text-xs text-accent">
          ({puzzle.bankEdits.length} swap{puzzle.bankEdits.length === 1 ? '' : 's'})
        </span>
      )}
    </span>
  );
}
