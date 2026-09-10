/**
 * Presentation tier. The composition root (planning.md 5, D).
 *
 * The **only** file that names concrete implementations. Every test builds
 * `<App>` with stubs instead, which is why there is no mocking framework in
 * this project and no `vi.mock` anywhere.
 */

import { StrictMode, Suspense, lazy } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';
import { HttpPuzzleRepository } from './data/httpPuzzleRepository';
import { LocalStorageProgressStore } from './data/localStorageProgressStore';
import './index.css';

const root = document.getElementById('root');
if (root === null) throw new Error('#root is missing from index.html');

// BASE_URL is '/Linkage/' in production and '/' in dev — the GitHub Pages
// subpath lives in vite.config.ts and nowhere else (Risk #7).
const repo = new HttpPuzzleRepository(import.meta.env.BASE_URL);
const store = new LocalStorageProgressStore();

/**
 * The admin tool exists only in development (planning.md 16.5).
 *
 * `import.meta.env.DEV` is replaced with the literal `false` at build time, so
 * the branch below is dead code in production and Rollup drops the dynamic
 * import with it — the admin never reaches `dist/`, let alone GitHub Pages.
 *
 * There is no server-side gate on the admin, so a deployed one would be an open
 * door onto the answer key. `scripts/assert-no-admin.mjs` runs on every build
 * and fails it if any of this survives, because a tree-shake that silently
 * stops working produces a deploy that looks completely normal.
 *
 * No router: two screens do not justify the dependency.
 */
const AdminApp = import.meta.env.DEV
  ? lazy(() => import('./admin/AdminApp').then((m) => ({ default: m.AdminApp })))
  : null;

const isAdminRoute =
  import.meta.env.DEV && window.location.pathname.replace(/\/+$/, '').endsWith('/admin');

createRoot(root).render(
  <StrictMode>
    {isAdminRoute && AdminApp !== null ? (
      <Suspense fallback={null}>
        <AdminApp />
      </Suspense>
    ) : (
      <App repo={repo} store={store} />
    )}
  </StrictMode>,
);
