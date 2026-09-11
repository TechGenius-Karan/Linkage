/**
 * A chain, sideways, with its weakest rung showing (docs/admin.md 10.2).
 *
 * The first version stacked six words vertically. That cost ~280px of height
 * for six short words, which is why only one puzzle fitted on screen — and one
 * puzzle at a time is what made 867 candidates feel unreachable.
 *
 * The bar under each link is not decoration. `MIN_EDGE_WEIGHT` gates a path on
 * its **weakest** edge because one weak link is what makes a chain feel unfair,
 * and 45 verdicts in, `badLink` says reviewers reject on exactly that — 13 of
 * 14 rejections named a rung in the opening half. So the weakest rung is drawn
 * loudest, and the eye lands where the decision is.
 */

import type { WordEdit } from './adminClient';

/** Weights run ~2 (the floor) to ~12. An absolute scale, not per-chain: a
 *  uniformly weak chain should *look* weak, not be rescaled into looking fine. */
const FULL_SCALE = 10;

export interface LadderProps {
  chain: string[];
  /** One per link; `chain[i] -> chain[i+1]`. */
  weights: number[];
  relations: string[][];
  /** Rungs resting on the reviewer's word rather than ConceptNet's. */
  asserted?: number[];
  badLink?: number | null;
  onMarkLink?: (index: number) => void;
  edits?: WordEdit[];
}

export function Ladder({
  chain,
  weights,
  relations,
  asserted = [],
  badLink = null,
  onMarkLink,
  edits = [],
}: LadderProps) {
  const weakest = weights.length > 0 ? Math.min(...weights) : 0;
  const changed = new Set(edits.map((e) => e.added));

  return (
    <ol className="flex flex-wrap items-center gap-x-0.5 gap-y-1">
      {chain.map((word, i) => {
        const endpoint = i === 0 || i === chain.length - 1;
        return (
          <li key={`${word}-${i}`} className="flex items-center gap-0.5">
            <span
              className={`font-word text-[15px] leading-tight ${
                endpoint ? 'font-semibold uppercase tracking-wide' : ''
              } ${changed.has(word) ? 'underline decoration-accent decoration-dotted underline-offset-4' : ''}`}
            >
              {word}
            </span>
            {i < chain.length - 1 && (
              <Rung
                index={i}
                weight={weights[i]}
                relations={relations[i] ?? []}
                from={word}
                to={chain[i + 1] ?? ''}
                isWeakest={weights[i] === weakest}
                isAsserted={asserted.includes(i)}
                selected={badLink === i}
                onMark={onMarkLink}
              />
            )}
          </li>
        );
      })}
    </ol>
  );
}

interface RungProps {
  index: number;
  weight: number | undefined;
  relations: string[];
  from: string;
  to: string;
  isWeakest: boolean;
  isAsserted: boolean;
  selected: boolean;
  onMark: ((index: number) => void) | undefined;
}

function Rung({
  index,
  weight,
  relations,
  from,
  to,
  isWeakest,
  isAsserted,
  selected,
  onMark,
}: RungProps) {
  const value = weight ?? 0;
  const fill = Math.max(6, Math.min(100, (value / FULL_SCALE) * 100));
  // Relations matter when adjudicating a doubtful link, not while scanning —
  // so they live in the tooltip rather than on the card.
  const label = isAsserted
    ? `${from} → ${to} — your word, not ConceptNet's`
    : `${from} → ${to} — ${value.toFixed(1)} · ${relations.join('/') || 'no relation'}`;

  const bar = (
    <span className="flex w-11 flex-col items-center gap-[3px]" aria-hidden="true">
      <span className="font-data text-[10px] leading-none text-ink-muted">
        {isAsserted ? '—' : value.toFixed(1)}
      </span>
      <span className="h-[3px] w-full overflow-hidden rounded-full bg-rule">
        <span
          className={`block h-full rounded-full ${
            selected
              ? 'bg-heart'
              : isAsserted
                ? 'bg-accent opacity-50'
                : isWeakest
                  ? 'bg-heart opacity-70'
                  : 'bg-accent opacity-45'
          }`}
          style={{ width: isAsserted ? '100%' : `${fill}%` }}
        />
      </span>
    </span>
  );

  if (onMark === undefined) {
    return (
      <span className="px-0.5" title={label}>
        {bar}
      </span>
    );
  }
  return (
    <button
      type="button"
      onClick={() => onMark(index)}
      aria-pressed={selected}
      aria-label={`Mark link ${index + 1}, ${from} to ${to}, as the weak one`}
      title={`${label} — click to blame this rung`}
      className={`ring-focus rounded px-0.5 py-1 ${selected ? '' : 'hover:bg-accent-sub'}`}
    >
      {bar}
    </button>
  );
}
