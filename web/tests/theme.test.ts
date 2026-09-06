/**
 * The pre-paint theme script (docs/design.md 2.1).
 *
 * `index.html` contains a hand-written script that TypeScript never compiles
 * and the bundler never rewrites. It reads the same storage key the settings
 * control writes — so a rename on the TypeScript side would leave the page
 * flashing the wrong background on every load, with nothing failing anywhere.
 *
 * These assertions are cheap and guard the one thing nothing else can see.
 */

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { THEME_KEY } from '../src/engine/types';

const html = readFileSync(fileURLToPath(new URL('../index.html', import.meta.url)), 'utf-8');

/** Just the inline script, so a match in a comment cannot satisfy a test. */
const inlineScript = (() => {
  const match = /<script>([\s\S]*?)<\/script>/.exec(html);
  if (match === null) throw new Error('index.html has no inline script');
  return match[1] ?? '';
})();

describe('pre-paint theme script', () => {
  it('reads the same key the app writes', () => {
    expect(inlineScript).toContain(`'${THEME_KEY}'`);
  });

  it('sets data-theme, which is what the CSS selectors key on', () => {
    expect(inlineScript).toMatch(/dataset\.theme|setAttribute\(\s*['"]data-theme/);
  });

  it('guards localStorage access', () => {
    // Safari private mode throws on access, and an uncaught throw in a
    // synchronous head script stops the page dead before it renders.
    expect(inlineScript).toMatch(/try\s*\{/);
    expect(inlineScript).toMatch(/catch/);
  });

  it('honours only light and dark, so `system` and garbage fall through', () => {
    expect(inlineScript).toContain("'light'");
    expect(inlineScript).toContain("'dark'");
  });

  it('runs in the head, before the module bundle', () => {
    const headEnd = html.indexOf('</head>');
    const module = html.indexOf('<script type="module"');
    const inline = html.indexOf('<script>');
    expect(inline).toBeGreaterThan(-1);
    expect(inline).toBeLessThan(headEnd);
    expect(inline).toBeLessThan(module);
  });

  it('stays inline — an external file would be a request before first paint', () => {
    expect(inlineScript.trim().length).toBeGreaterThan(0);
    expect(inlineScript).not.toContain('import');
  });
});
