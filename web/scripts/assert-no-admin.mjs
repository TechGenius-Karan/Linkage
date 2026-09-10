/**
 * The admin must never ship (planning.md 16.5).
 *
 * There is no server-side gate on the review tool, so a deployed one is an open
 * door onto the answer key. `main.tsx` drops it behind `import.meta.env.DEV`,
 * which Rollup tree-shakes — but a tree-shake that silently stops working
 * produces a deploy that looks completely normal and gives no sign at all.
 *
 * So this runs on every build and fails it. Deliberately a build step rather
 * than a test: a test can be skipped, and this is the one that must not be.
 */

import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const DIST = fileURLToPath(new URL('../dist/', import.meta.url));

/** Strings that only exist because admin code is present. */
const FORBIDDEN = [
  '/api/admin/',
  'Linkage review',
  'linkage admin',
  'adminClient',
  'ReviewCard',
];

function walk(dir) {
  const out = [];
  for (const entry of readdirSync(dir)) {
    const path = join(dir, entry);
    out.push(...(statSync(path).isDirectory() ? walk(path) : [path]));
  }
  return out;
}

let files;
try {
  files = walk(DIST);
} catch {
  console.error(`assert-no-admin: no dist/ to check at ${DIST}`);
  process.exit(1);
}

const hits = [];
for (const file of files) {
  if (!/\.(js|css|html|map)$/.test(file)) continue;
  const text = readFileSync(file, 'utf-8');
  for (const needle of FORBIDDEN) {
    if (text.includes(needle)) hits.push(`${file}: ${needle}`);
  }
}

if (hits.length > 0) {
  console.error('\nassert-no-admin: ADMIN CODE FOUND IN THE PRODUCTION BUILD\n');
  for (const hit of hits) console.error(`  ${hit}`);
  console.error('\nThe review tool has no authentication. Do not deploy this.\n');
  process.exit(1);
}

console.log(`assert-no-admin: clean (${files.length} files checked)`);
