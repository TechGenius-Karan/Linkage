import { defineConfig } from 'vitest/config';

// Deliberately separate from vite.config.ts. Vitest resolves its own copy
// of Vite, so a shared config file makes the two Plugin types structurally
// incompatible under exactOptionalPropertyTypes. These are node-environment
// unit tests -- they need neither the React plugin nor Tailwind.
export default defineConfig({
  test: {
    environment: 'node',
    include: ['tests/**/*.test.ts', 'tests/**/*.test.tsx'],
  },
});
