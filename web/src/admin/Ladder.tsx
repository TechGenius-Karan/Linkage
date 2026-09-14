/**
 * A chain, sideways (docs/admin.md 10.2).
 *
 * It used to print the edge weight between every pair of words, as a number
 * and a bar. Both are gone. The reviewer is judging whether two words *read*
 * as related to a person; the weight is a fact about ConceptNet's confidence,
 * which the generator needs and a reader does not. Five numbers per card
 * across five cards is twenty-five things to not look at.
 *
 * What survives is the click target. `badLink` — which rung failed — is the
 * most valuable thing this tool collects, so the connector stays as a rule you
 * can press. Weight lives in the tooltip for the rare case anyone wants it.
 */

import type { WordEdit } from './adminClient';

export interface LadderProps {
  chain: string[];
  weights: number[];
  relations: string[][];
  /** Rungs resting on the reviewer's word rather than ConceptNet's. */
  asserted?: number[];
  /**
   * The marked link, or a marked span (docs/admin.md 5.4) — shift-clicking a
   * second link extends `badLink` into `[lo, hi]` rather than replacing it.
   */
  badLink?: number | null;
  range?: [number, number] | null;
  /** `extend` is true on a shift-click — grow the span instead of replacing it. */
  onMarkLink?: ((index: number, extend: boolean) => void) | undefined;
  edits?: WordEdit[];
  /**
   * Softens the interior words.
   *
   * On the review screen every word is under judgement and they all read at
   * full strength. In a *list* you are identifying a puzzle to act on, and
   * what identifies it is its endpoints — so the four in between step back.
   * Six words at identical weight is what made the schedule screen tiring.
   */
  tone?: 'judge' | 'list';
}

export function Ladder({
  chain,
  weights,
  relations,
  asserted = [],
  badLink = null,
  range = null,
  onMarkLink,
  edits = [],
  tone = 'judge',
}: LadderProps) {
  const changed = new Set(edits.map((e) => e.added));

  return (
    <ol className={`adm-chain${tone === 'list' ? ' adm-chain--list' : ''}`}>
      {chain.map((word, i) => {
        const endpoint = i === 0 || i === chain.length - 1;
        return (
          <li key={`${word}-${i}`} className="adm-link">
            <span
              className={[
                'adm-word',
                endpoint ? 'adm-word--end' : '',
                changed.has(word) ? 'adm-word--edited' : '',
              ]
                .filter(Boolean)
                .join(' ')}
            >
              {word}
            </span>
            {i < chain.length - 1 && (
              <Rung
                index={i}
                from={word}
                to={chain[i + 1] ?? ''}
                weight={weights[i]}
                relations={relations[i] ?? []}
                isAsserted={asserted.includes(i)}
                selected={range !== null ? i >= range[0] && i <= range[1] : badLink === i}
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
  from: string;
  to: string;
  weight: number | undefined;
  relations: string[];
  isAsserted: boolean;
  selected: boolean;
  onMark: ((index: number, extend: boolean) => void) | undefined;
}

function Rung({ index, from, to, weight, relations, isAsserted, selected, onMark }: RungProps) {
  // Kept in the tooltip only. Nothing about it belongs on the page.
  const detail = isAsserted
    ? `${from} → ${to} — your word, not ConceptNet's`
    : `${from} → ${to}${weight === undefined ? '' : ` — ${weight.toFixed(1)} ${relations.join('/')}`}`;

  const className = `adm-rung${isAsserted ? ' adm-rung--asserted' : ''}`;

  if (onMark === undefined) {
    return <span className={`${className} adm-rung--static`} title={detail} aria-hidden="true" />;
  }
  return (
    <button
      type="button"
      className={className}
      onClick={(e) => onMark(index, e.shiftKey)}
      aria-pressed={selected}
      aria-label={`Mark the link from ${from} to ${to} as the one that fails`}
      title={`${detail} — click to blame this link, shift-click a second one to span both`}
    />
  );
}
