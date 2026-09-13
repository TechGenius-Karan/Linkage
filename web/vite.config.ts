import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwind from '@tailwindcss/vite';

// Netlify serves the site at its domain root (both the *.netlify.app
// subdomain and a bought custom domain later), not a project subpath, so
// `base` is just Vite's default. Left explicit rather than omitted because
// this is the one place the deploy path is written down —
// HttpPuzzleRepository reads the same value via import.meta.env.BASE_URL
// rather than a hardcoded path, so a future subpath (or another host)
// would only ever mean changing this one line (planning.md Risk #7,
// docs/deployment.md).
export default defineConfig({
  base: '/',
  plugins: [react(), tailwind()],
  server: {
    // The admin's Python server (`linkage admin`) lives on another port.
    // Proxying keeps the browser same-origin, so CORS never enters the
    // picture and the client needs no base URL (planning.md 16.3).
    proxy: {
      '/api/admin': { target: 'http://127.0.0.1:8787', changeOrigin: false },
    },
  },
});
