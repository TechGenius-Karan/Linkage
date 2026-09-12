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
 *
 * The header used to carry three counts nobody asked for ("30 free in the run",
 * "1 shipped · through 2026-10-01"). They are gone: the days themselves say how
 * many are free, and what already shipped is the Upcoming screen's business.
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

  if (load.kind === 'loading') return <p className="adm-empty">Loading the pool…</p>;
  if (load.kind === 'error') return <p className="adm-refusal">{load.message}</p>;

  const { pooled, slots, openDays } = load.data;
  const free = slots.filter((s) => s.hash === null);
  const offered = showAllDays ? free.map((s) => s.date) : openDays;

  return (
    <div>
      {error !== null && <p className="adm-refusal">{error}</p>}

      {warnings !== null && (
        <div className="adm-panel">
          <div className="adm-section" style={{ margin: 0 }}>
            <h2 className="adm-h2">Scheduled for {format(warnings.date)}</h2>
            <button
              type="button"
              className="adm-btn adm-btn--quiet"
              onClick={() => setWarnings(null)}
            >
              Dismiss
            </button>
          </div>
          {warnings.lines.length === 0 ? (
            <p className="adm-note">Nothing clashes on that day.</p>
          ) : (
            warnings.lines.map((line) => (
              <p key={line} className="adm-refusal">
                {line}
              </p>
            ))
          )}
        </div>
      )}

      <section>
        <div className="adm-section">
          <h2 className="adm-h2">Next open days</h2>
        </div>
        {openDays.length === 0 ? (
          <p className="adm-note">Every day in the run is taken.</p>
        ) : (
          <div className="adm-days">
            {openDays.map((day) => (
              <span key={day} className="adm-day adm-day--static">
                {format(day)}
              </span>
            ))}
          </div>
        )}
      </section>

      <section>
        <div className="adm-section">
          <h2 className="adm-h2">Waiting for a date</h2>
          <span className="adm-meta">{pooled.length}</span>
        </div>
        {pooled.length === 0 ? (
          <p className="adm-empty">Nothing approved yet.</p>
        ) : (
          pooled.map((puzzle) => (
            <article key={puzzle.hash} className="adm-row">
              <Ladder
                chain={puzzle.chain}
                weights={puzzle.linkWeights}
                relations={puzzle.relations}
                edits={puzzle.bankEdits}
              />
              <div style={{ display: 'flex', gap: '0.375rem', alignItems: 'center' }}>
                {puzzle.manualEdges.length > 0 && (
                  <span className="adm-meta" title="Ships a link you asserted">
                    {puzzle.manualEdges.length} asserted
                  </span>
                )}
                <button
                  type="button"
                  className="adm-btn"
                  disabled={busy || free.length === 0}
                  onClick={() => setPicking(picking === puzzle.hash ? null : puzzle.hash)}
                  aria-expanded={picking === puzzle.hash}
                  title={free.length === 0 ? 'Every slot in the run is taken' : undefined}
                >
                  Schedule
                </button>
                <button
                  type="button"
                  className="adm-btn adm-btn--quiet"
                  disabled={busy}
                  onClick={() => void act(() => sendBackPuzzle(puzzle.hash))}
                  title="Back to the review queue, into its own lane"
                >
                  Send back
                </button>
              </div>

              {picking === puzzle.hash && (
                <div className="adm-days" style={{ flexBasis: '100%' }}>
                  {offered.map((day) => (
                    <button
                      key={day}
                      type="button"
                      className="adm-day"
                      disabled={busy}
                      onClick={() =>
                        void act(async () => {
                          const result = await schedulePuzzle(puzzle.hash, day);
                          setWarnings({ date: result.date, lines: result.warnings });
                          setPicking(null);
                        })
                      }
                    >
                      {format(day)}
                    </button>
                  ))}
                  {free.length > offered.length && (
                    <button
                      type="button"
                      className="adm-btn adm-btn--quiet"
                      onClick={() => setShowAllDays(true)}
                    >
                      {free.length - offered.length} more
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

/** `2026-10-04` → `4 Oct`. A reviewer picks a day, not an ISO string. */
export function format(date: string): string {
  const parsed = new Date(`${date}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return date;
  return `${parsed.getDate()} ${parsed.toLocaleString('en', { month: 'short' })}`;
}
