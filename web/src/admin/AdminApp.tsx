/**
 * The review tool's shell (docs/admin.md 12).
 *
 * Three screens, and no router for three screens — that would be a dependency
 * earning nothing in a tool one person runs on localhost.
 *
 * `admin.css` is imported here rather than from the app's stylesheet, so the
 * tokens and webfonts travel with this lazy chunk and never reach a player.
 */

import { useCallback, useEffect, useState } from 'react';
import './admin.css';
import { fetchQueue, type QueueCounts } from './adminClient';
import { PoolPage } from './PoolPage';
import { ReviewPage } from './ReviewPage';
import { UpcomingPage } from './UpcomingPage';

type View = 'review' | 'schedule' | 'upcoming';
type Theme = 'dark' | 'light';

const TABS: readonly { id: View; label: string }[] = [
  { id: 'review', label: 'Review' },
  { id: 'schedule', label: 'Schedule' },
  { id: 'upcoming', label: 'Upcoming' },
];

/**
 * The admin's own key, separate from the game's `linkage:v1:theme`.
 *
 * They are genuinely different preferences: the game is read for two minutes
 * in whatever light the player is in, the admin for an hour at a desk. Sharing
 * one key would mean changing one to change the other.
 */
const THEME_KEY = 'linkage:v1:admin-theme';

/** Dark unless told otherwise, and never the OS — see admin.css. */
function storedTheme(): Theme {
  try {
    return localStorage.getItem(THEME_KEY) === 'light' ? 'light' : 'dark';
  } catch {
    return 'dark';
  }
}

export function AdminApp() {
  const [view, setView] = useState<View>('review');
  const [counts, setCounts] = useState<QueueCounts | null>(null);
  const [theme, setTheme] = useState<Theme>(storedTheme);

  useEffect(() => {
    try {
      localStorage.setItem(THEME_KEY, theme);
    } catch {
      // A tool that refuses to change theme because storage is full would be
      // a worse failure than simply not remembering.
    }
  }, [theme]);

  // Scheduling and sending back both change the header, from screens that do
  // not own it. Cheaper than lifting the whole queue into this component.
  const refreshCounts = useCallback(() => {
    void fetchQueue()
      .then((data) => setCounts(data.counts))
      .catch(() => undefined);
  }, []);

  return (
    <div className="adm" data-adm-theme={theme}>
      <div className="adm-page">
        <header className="adm-head">
          <div>
            <h1 className="adm-title">Linkage review</h1>
            {/* One line, three numbers. The rest was noise. */}
            {counts !== null && (
              <p className="adm-subhead">
                {counts.approved} approved &nbsp;·&nbsp; {counts.scheduled} dated &nbsp;·&nbsp;{' '}
                {counts.rejected} rejected
              </p>
            )}
          </div>
          <button
            type="button"
            className="adm-btn adm-btn--theme"
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
            title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
          >
            {theme === 'dark' ? 'Light' : 'Dark'}
          </button>
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
