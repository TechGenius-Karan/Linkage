/**
 * Presentation tier. The composition root (planning.md 5, D).
 *
 * The **only** file that names concrete implementations. Every test builds
 * `<App>` with stubs instead, which is why there is no mocking framework in
 * this project and no `vi.mock` anywhere.
 */

import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';
import { HttpPuzzleRepository } from './data/httpPuzzleRepository';
import './index.css';

const root = document.getElementById('root');
if (root === null) throw new Error('#root is missing from index.html');

// BASE_URL is '/Linkage/' in production and '/' in dev — the GitHub Pages
// subpath lives in vite.config.ts and nowhere else (Risk #7).
const repo = new HttpPuzzleRepository(import.meta.env.BASE_URL);

createRoot(root).render(
  <StrictMode>
    <App repo={repo} />
  </StrictMode>,
);
