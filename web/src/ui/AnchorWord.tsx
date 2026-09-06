/**
 * Presentation tier. The two fixed words.
 *
 * Display casing is a CSS concern — `text-transform: uppercase` on `.anchor`.
 * The data is lowercase everywhere and stays that way (planning.md 3.1.1).
 */

export interface AnchorWordProps {
  word: string;
  position: 'start' | 'end';
}

export function AnchorWord({ word, position }: AnchorWordProps) {
  return (
    <div className="anchor" aria-label={`${position === 'start' ? 'Start' : 'End'} word, ${word}`}>
      {word}
    </div>
  );
}
