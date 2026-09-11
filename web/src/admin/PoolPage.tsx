/**
 * The approved pool, and choosing a date (docs/admin.md 2, 7, 8, 12.2).
 *
 * Approving records taste; scheduling is a separate act. This is where the
 * second one happens, and the whole reason a decision carries `date: null`
 * until somebody deliberately fills it in.
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
  sendBackPuzzle,
  type PoolResponse,
} from './adminClient';
import { Ladder } from './Ladder';

type Load =
  | { kind: 'loading' }
  | { kind: 'ready'; data: PoolResponse }
  | { kind: 'error'; message: string };

export interface PoolPageProps {
  /** Refresh the header counts, which scheduling and sending back both change. */
  onChanged: () => void;
}

export function PoolPage({ onChanged }: PoolPageProps) {
  const [load, setLoad] = useState<Load>({ kind: 'loading' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [picking, setPicking] = useState<string | null>(null);
  const [showAllDays, setShowAllDays] = useState(false);
  /** Corpus warnings from the last schedule — docs/admin.md 7's whole point. */
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

  const { pooled, slots, openDays, archive } = load.data;
  const free = slots.filter((s) => s.hash === null);
  const offered = showAllDays ? free.map((s) => s.date) : openDays;
  const taken = slots.filter((s) => s.hash !== null).map((s) => s.date);

  return (
    <div className="flex flex-col gap-5">
      {/* The seven-day strip: a week is the unit a person plans in (12.2). */}
      <section className="rounded-lg border border-rule bg-surface p-3">
        <div className="mb-2 flex items-baseline justify-between gap-3">
          <h2 className="text-sm font-semibold">
            Next open days{' '}
            <span className="font-data text-[10px] font-normal text-ink-muted">
              {free.length} free in the run
            </span>
          </h2>
          <span className="font-data text-[10px] text-ink-muted">
            {archive.count} shipped
            {archive.lastDate !== null ? ` · through ${archive.lastDate}` : ''}
          </span>
        </div>
        <div className="flex flex-wrap gap-1">
          {openDays.map((day) => (
            <span
              key={day}
              className="rounded border border-rule px-2 py-1 font-data text-xs tabular-nums"
            >
              {day.slice(5)}
            </span>
          ))}
          {openDays.length === 0 && (
            <span className="text-[13px] text-ink-muted">
              Every day in the run is taken. Run <code className="font-data">linkage export</code>.
            </span>
          )}
        </div>
        {taken.length > 0 && (
          // Skipped days named rather than hidden, so a gap is visible before
          // export reports it (docs/admin.md 8).
          <p className="mt-2 font-data text-[10px] text-ink-muted">
            taken: {taken.map((d) => d.slice(5)).join(', ')}
          </p>
        )}
      </section>

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
              className="ring-focus rounded px-1.5 text-xs underline"
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

      <section className="flex flex-col gap-2">
        <h2 className="text-sm font-semibold">
          Approved, waiting for a date{' '}
          <span className="font-data text-xs font-normal text-ink-muted">{pooled.length}</span>
        </h2>
        {pooled.length === 0 ? (
          <p className="text-[13px] text-ink-muted">
            The pool is empty. Approve some candidates in the queue.
          </p>
        ) : (
          pooled.map((puzzle) => (
            <article
              key={puzzle.hash}
              className="flex flex-col gap-2 rounded-lg border border-rule bg-surface px-3 py-2"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <Ladder
                  chain={puzzle.chain}
                  weights={puzzle.linkWeights}
                  relations={puzzle.relations}
                  edits={puzzle.bankEdits}
                />
                <div className="flex shrink-0 items-center gap-1.5">
                  <button
                    type="button"
                    disabled={busy || free.length === 0}
                    onClick={() => setPicking(picking === puzzle.hash ? null : puzzle.hash)}
                    aria-expanded={picking === puzzle.hash}
                    title={free.length === 0 ? 'Every slot in the run is taken' : undefined}
                    className="ring-focus rounded-md border border-rule px-2 py-1 text-xs disabled:opacity-40"
                  >
                    Schedule
                  </button>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void act(() => sendBackPuzzle(puzzle.hash))}
                    title="Back to the review queue, into its own lane"
                    className="ring-focus rounded-md px-2 py-1 text-xs underline disabled:opacity-40"
                  >
                    Send back
                  </button>
                </div>
              </div>

              {puzzle.manualEdges.length > 0 && (
                <p className="font-data text-[10px] text-accent">
                  {puzzle.manualEdges.length} hand-authored link
                  {puzzle.manualEdges.length === 1 ? '' : 's'}
                </p>
              )}

              {picking === puzzle.hash && (
                <div className="flex flex-wrap items-center gap-1">
                  {offered.map((day) => (
                    <button
                      key={day}
                      type="button"
                      disabled={busy}
                      onClick={() =>
                        void act(async () => {
                          const result = await schedulePuzzle(puzzle.hash, day);
                          setWarnings({ date: result.date, lines: result.warnings });
                          setPicking(null);
                        })
                      }
                      className="ring-focus rounded border border-rule px-2 py-1 font-data text-xs tabular-nums hover:bg-accent-sub disabled:opacity-40"
                    >
                      {day.slice(5)}
                    </button>
                  ))}
                  {free.length > offered.length && (
                    <button
                      type="button"
                      onClick={() => setShowAllDays(true)}
                      className="ring-focus rounded px-1.5 py-1 text-xs underline"
                    >
                      +{free.length - offered.length} more
                    </button>
                  )}
                </div>
              )}
            </article>
          ))
        )}
      </section>
    </div>
  );
}
