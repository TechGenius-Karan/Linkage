/**
 * The review tool's shell (docs/admin.md 12).
 *
 * Three screens, and no router for three screens — that would be a dependency
 * earning nothing in a tool one person runs on localhost.
 *
 * `admin.css` is imported here rather than from the app's stylesheet, so the
 * tokens and webfonts travel with this lazy chunk and never reach a player.
 */

import { useCallback, useState } from 'react';
import './admin.css';
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
    <div className="adm">
      <div className="adm-page">
        <header>
          <h1 className="adm-title">Linkage review</h1>
          {/* One line, three numbers. The rest was noise. */}
          {counts !== null && (
            <p className="adm-meta" style={{ marginTop: '0.375rem' }}>
              {counts.approved} approved &nbsp;·&nbsp; {counts.scheduled} dated &nbsp;·&nbsp;{' '}
              {counts.rejected} rejected
            </p>
          )}
        </header>

        <nav className="adm-tabs">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              className="adm-tab"
              onClick={() => setView(tab.id)}
              aria-current={view === tab.id ? 'page' : undefined}
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
