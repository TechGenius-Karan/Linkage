import js from '@eslint/js';
import tseslint from 'typescript-eslint';

/**
 * The dependency rule, enforced (planning.md 4.2).
 *
 * `engine/` is the domain tier. It may import only its own types. The moment
 * it imports React, touches the DOM, or calls `fetch`, the game logic stops
 * being testable as plain functions and the tier boundary becomes a comment
 * rather than a fact.
 *
 * This is a build failure on purpose — a convention we hope to remember is not
 * an architecture.
 */
export default tseslint.config(
  { ignores: ['dist', 'node_modules'] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ['src/**/*.{ts,tsx}', 'tests/**/*.{ts,tsx}'],
    languageOptions: {
      parserOptions: { ecmaVersion: 2022, sourceType: 'module' },
    },
  },
  {
    files: ['src/engine/**/*.ts'],
    rules: {
      'no-restricted-imports': [
        'error',
        {
          paths: [
            { name: 'react', message: 'engine/ is the domain tier — no React.' },
            { name: 'react-dom', message: 'engine/ is the domain tier — no React.' },
          ],
          patterns: [
            { group: ['../ui/*', '../data/*'], message: 'Dependencies point inward.' },
          ],
        },
      ],
      'no-restricted-globals': [
        'error',
        { name: 'window', message: 'engine/ is the domain tier — no DOM.' },
        { name: 'document', message: 'engine/ is the domain tier — no DOM.' },
        { name: 'localStorage', message: 'engine/ declares ProgressStore; data/ implements it.' },
        { name: 'fetch', message: 'engine/ declares PuzzleRepository; data/ implements it.' },
      ],
    },
  },
  {
    files: ['src/data/**/*.ts'],
    rules: {
      'no-restricted-imports': [
        'error',
        {
          patterns: [{ group: ['../ui/*'], message: 'data/ must not import presentation.' }],
        },
      ],
    },
  },
);
