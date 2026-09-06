/**
 * Presentation tier. The only icons in the product (docs/design.md 7).
 *
 * Built from circles, lines and a glyph on purpose: a single stroke weight, no
 * filled shapes, nothing that reads as a brand mark competing with the wordmark
 * beside them.
 *
 * These are placeholders for the reference art still to come. The shapes may
 * change; the 20x20 box, 1.6 stroke and `currentColor` should not.
 */

import type { ReactNode } from 'react';

function Svg({ children }: { children: ReactNode }) {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      aria-hidden="true"
      focusable="false"
    >
      {children}
    </svg>
  );
}

/** Hint — a lamp reduced to its two primitives. */
export function HintIcon() {
  return (
    <Svg>
      <circle cx="10" cy="8" r="4.5" />
      <line x1="7.5" y1="15.5" x2="12.5" y2="15.5" />
    </Svg>
  );
}

/** Statistics — the distribution histogram the panel actually shows. */
export function StatsIcon() {
  return (
    <Svg>
      <line x1="5" y1="15" x2="5" y2="10" />
      <line x1="10" y1="15" x2="10" y2="5" />
      <line x1="15" y1="15" x2="15" y2="12" />
    </Svg>
  );
}

/** How to play. A glyph inside a circle beats hand-drawing a question mark. */
export function HelpIcon() {
  return (
    <Svg>
      <circle cx="10" cy="10" r="7.2" />
      <text
        x="10"
        y="14.2"
        textAnchor="middle"
        fontSize="10"
        fontWeight="600"
        fontFamily="var(--type-ui)"
        fill="currentColor"
        stroke="none"
      >
        ?
      </text>
    </Svg>
  );
}

/** Settings — sliders, not a gear. A gear needs a path; this needs four shapes. */
export function SettingsIcon() {
  return (
    <Svg>
      <line x1="4" y1="7" x2="16" y2="7" />
      <line x1="4" y1="13" x2="16" y2="13" />
      <circle cx="12.5" cy="7" r="2" />
      <circle cx="7.5" cy="13" r="2" />
    </Svg>
  );
}
