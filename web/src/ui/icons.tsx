/**
 * Presentation tier. The only icons in the product (docs/design.md 7).
 *
 * Single stroke weight, no filled shapes, nothing that reads as a brand mark
 * competing with the wordmark beside them. Rendered at a 24x24 CSS box off a
 * matching 24-unit viewBox, so a gear needs no manual coordinate rescaling to
 * sit next to the simpler icons.
 */

import type { ReactNode } from 'react';

function Svg({ children, size = 24 }: { children: ReactNode; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {children}
    </svg>
  );
}

/** Hint — a bulb and base, not just a circle and a line. */
export function HintIcon({ size = 24 }: { size?: number } = {}) {
  return (
    <Svg size={size}>
      <circle cx="12" cy="9.5" r="6" />
      <rect x="9.25" y="14" width="5.5" height="3.5" rx="1" />
      <line x1="9.5" y1="20" x2="14.5" y2="20" />
    </Svg>
  );
}

/** Statistics — three ascending bars, the shape the panel's own chart shows. */
export function StatsIcon() {
  return (
    <Svg>
      <rect x="3.5" y="14" width="4.5" height="6" rx="1.2" />
      <rect x="10" y="10" width="4.5" height="10" rx="1.2" />
      <rect x="16.5" y="4" width="4.5" height="16" rx="1.2" />
    </Svg>
  );
}

/** How to play — a hand-drawn hook and dot, not a font glyph. */
export function HelpIcon() {
  return (
    <Svg>
      <circle cx="12" cy="12" r="10" />
      <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </Svg>
  );
}

/** Check — a single confirmed guess, badged in accent (how-to-play). */
export function CheckIcon() {
  return (
    <Svg size={18}>
      <path d="M4 12.5l5 5L20 6" strokeWidth="3" />
    </Svg>
  );
}

/** Timer — an actual clock, for "guess freely" (how-to-play). */
export function TimerIcon({ size = 30 }: { size?: number } = {}) {
  return (
    <Svg size={size}>
      <circle cx="12" cy="13" r="8.5" />
      <path d="M12 9v4l3 2" />
      <path d="M9.5 2h5" />
    </Svg>
  );
}

/** Streak — a flame, for the stats panel's best-streak row. */
export function FireIcon({ size = 24 }: { size?: number } = {}) {
  return (
    <Svg size={size}>
      <path d="M8.5 14.5a2.5 2.5 0 0 0 2.5-2.5c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z" />
    </Svg>
  );
}

/** Settings — an actual gear now. */
export function SettingsIcon() {
  return (
    <Svg>
      <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
      <circle cx="12" cy="12" r="3" />
    </Svg>
  );
}

/**
 * No puzzle yet — a resting crescent moon with a twinkle. The one deliberate
 * exception to this file's own "no filled shapes" rule above: every other
 * icon here is a small functional control living next to the wordmark, but
 * this one is the entire empty-state illustration, at 4x the size, meant to
 * read as a warm little nightlight rather than a nav glyph. Filled + glowing
 * (`.moon-glow`/`.moon-halo`, index.css) so it earns that size instead of
 * just looking like a bigger outline.
 */
export function RestingMoonIcon({
  size = 56,
  className,
}: {
  size?: number;
  className?: string;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      aria-hidden="true"
      focusable="false"
      className={className}
    >
      <path
        fill="currentColor"
        d="M9.528 1.718a.75.75 0 0 1 .162.819A8.97 8.97 0 0 0 9 6a9 9 0 0 0 9 9 8.97 8.97 0 0 0 3.463-.69.75.75 0 0 1 .981.98 10.503 10.503 0 0 1-9.694 6.46c-5.799 0-10.5-4.701-10.5-10.5 0-4.368 2.667-8.112 6.46-9.694a.75.75 0 0 1 .818.162Z"
      />
      <path
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        d="M18 3v3.4M16.3 4.7h3.4"
      />
    </svg>
  );
}
