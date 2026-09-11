/**
 * The review tool's shell (docs/admin.md 12).
 *
 * Three screens, and no router for three screens — that would be a dependency
 * earning nothing in a tool one person runs on localhost.
 *
 *   REVIEW     five candidates, plus whatever was sent back
 *   SCHEDULE   approved and undated, plus the next seven open days
 *   UPCOMING   already dated, in date order
 */

import { useCallback, useState } from 'react';
import { fetchQueue, type QueueCounts } from './adminClient';
import { PoolPage } from './PoolPage';
import { ReviewPage } from './ReviewPage';
import { UpcomingPage } from './UpcomingPage';

type View = 'review' | 'schedule' | 'upcoming';

const TABS: readonly { id: View; label: string }[] = [
  { id: 'review', label: 'Review' },
  { id: 'schedule', label: 'Schedule' },
  { id: 'upcoming', label: 'Upcoming' },
];

export function AdminApp() {
  const [view, setView] = useState<View>('review');
  const [counts, setCounts] = useState<QueueCounts | null>(null);

  // Scheduling and sending back both change the header, from screens that do
  // not own it. Cheaper than lifting the whole queue into this component.
  const refreshCounts = useCallback(() => {
    void fetchQueue()
      .then((data) => setCounts(data.counts))
      .catch(() => undefined);
  }, []);

  return (
    <div className="flex min-h-screen justify-center px-4 py-6">
      <div className="flex w-full max-w-4xl flex-col gap-4">
        <header className="flex flex-wrap items-baseline justify-between gap-3">
          <h1 className="font-word text-xl font-semibold">Linkage review</h1>
          {counts !== null && (
            <span className="font-data text-[10px] text-ink-muted">
              {counts.pending} pending · {counts.approved} approved · {counts.scheduled}{' '}
              scheduled · {counts.rejected} rejected
              {counts.returned > 0 ? ` · ${counts.returned} sent back` : ''}
            </span>
          )}
        </header>

        <nav className="flex gap-1 border-b border-rule">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setView(tab.id)}
              aria-current={view === tab.id ? 'page' : undefined}
              className={`ring-focus -mb-px rounded-t-md border-b-2 px-3 py-1.5 text-[13px] ${
                view === tab.id
                  ? 'border-accent font-semibold text-accent'
                  : 'border-transparent text-ink-muted hover:text-ink'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>

        {view === 'review' && <ReviewPage onCounts={setCounts} />}
        {view === 'schedule' && <PoolPage onChanged={refreshCounts} />}
        {view === 'upcoming' && <UpcomingPage onChanged={refreshCounts} />}
      </div>
    </div>
  );
}
