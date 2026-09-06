import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwind from '@tailwindcss/vite';

// `base` must match the GitHub Pages project subpath or every asset 404s in
// production while working perfectly on localhost (planning.md Risk #7).
// HttpPuzzleRepository reads the same value via import.meta.env.BASE_URL, so
// this constant is the single place the deploy path is written down.
export default defineConfig({
  base: '/Linkage/',
  plugins: [react(), tailwind()],
});
