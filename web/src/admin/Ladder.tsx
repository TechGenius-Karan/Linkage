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
  badLink?: number | null;
  onMarkLink?: ((index: number) => void) | undefined;
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
  const changed = new Set(edits.map((e) => e.added));

  return (
    <ol className="adm-chain">
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
  from: string;
  to: string;
  weight: number | undefined;
  relations: string[];
  isAsserted: boolean;
  selected: boolean;
  onMark: ((index: number) => void) | undefined;
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
      onClick={() => onMark(index)}
      aria-pressed={selected}
      aria-label={`Mark the link from ${from} to ${to} as the one that fails`}
      title={`${detail} — click to blame this link`}
    />
  );
}
