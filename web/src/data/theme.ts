/**
 * Data tier. Applies and persists the theme preference (docs/design.md 2.1).
 *
 * Mirrors index.html's pre-paint script: only 'light'/'dark' ever land on the
 * DOM attribute; 'system' clears it so `color-scheme: light dark` (index.css)
 * takes back over.
 */

import { THEME_KEY, type ThemePreference } from '../engine/types';

export function getThemePreference(): ThemePreference {
  try {
    const stored = localStorage.getItem(THEME_KEY);
    if (stored === 'light' || stored === 'dark') return stored;
  } catch {
    // Storage disabled or unavailable -- fall through to system.
  }
  return 'system';
}

export function setThemePreference(pref: ThemePreference): void {
  if (pref === 'system') delete document.documentElement.dataset['theme'];
  else document.documentElement.dataset['theme'] = pref;

  try {
    if (pref === 'system') localStorage.removeItem(THEME_KEY);
    else localStorage.setItem(THEME_KEY, pref);
  } catch {
    // Preference just won't survive a reload; the toggle still works live.
  }
}
