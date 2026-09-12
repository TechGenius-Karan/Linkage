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
 */

import { useCallback, useEffect, useState } from 'react';
import { fetchPool, unschedulePuzzle, type PoolResponse } from './adminClient';
import { Ladder } from './Ladder';
import { format } from './PoolPage';

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

  if (load.kind === 'loading') return <p className="adm-empty">Loading the calendar…</p>;
  if (load.kind === 'error') return <p className="adm-refusal">{load.message}</p>;

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
    <div>
      {error !== null && <p className="adm-refusal">{error}</p>}

      <div className="adm-section">
        <h2 className="adm-h2">On the calendar</h2>
        <span className="adm-meta">
          {archive.count > 0 ? `${archive.count} already shipped` : 'nothing shipped yet'}
        </span>
      </div>

      {scheduled.length === 0 ? (
        <p className="adm-empty">
          Nothing dated. Export will propose days for whatever is in the pool.
        </p>
      ) : (
        <ol className="adm-list">
          {scheduled.map((puzzle) => (
            <li key={puzzle.hash} className="adm-row">
              <div className="adm-dated">
                <time dateTime={puzzle.date ?? undefined} className="adm-meta">
                  {puzzle.date === null ? '' : format(puzzle.date)}
                </time>
                <Ladder
                  chain={puzzle.chain}
                  weights={puzzle.linkWeights}
                  relations={puzzle.relations}
                  edits={puzzle.bankEdits}
                  tone="list"
                />
              </div>
              <div className="adm-cluster">
                {puzzle.manualEdges.length > 0 && (
                  <span className="adm-meta" title="Ships a link you asserted">
                    {puzzle.manualEdges.length} asserted
                  </span>
                )}
                <button
                  type="button"
                  className="adm-btn adm-btn--quiet"
                  disabled={busy}
                  onClick={() => void release(puzzle.hash)}
                  title="Off the calendar, back to the approved pool"
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
