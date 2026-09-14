/**
 * Rewriting a puzzle by hand (docs/admin.md 11).
 *
 * **The reviewer decides whether the puzzle still holds.** ConceptNet is wrong
 * often enough that most rejections say so outright, so a rung it has no edge
 * for is something to *tell* the reviewer about, not something to refuse. They
 * assert it and it ships with the puzzle as evidence.
 *
 * The machine keeps exactly one veto: a second valid arrangement, and the
 * chords that manufacture one. That is arithmetic over 7,920 orderings rather
 * than a matter of taste.
 *
 * Nothing here is saved. Edits live in component state until the puzzle is
 * approved, which is why the state machine has four states and not five.
 */

import { useState } from 'react';
import {
  fetchLinkFixes,
  fetchRangeFixes,
  fetchSwapOptions,
  previewEdit,
  type EditResponse,
  type LinkFixOption,
  type ManualEdge,
  type QueuePuzzle,
  type RangeFixOption,
  type SwapOption,
  type WordEdit,
} from './adminClient';

export interface PuzzleEditorProps {
  puzzle: QueuePuzzle;
  edits: WordEdit[];
  edges: ManualEdge[];
  /** The last preview, or null before anything has been changed. */
  state: EditResponse | null;
  onChange: (edits: WordEdit[], edges: ManualEdge[], state: EditResponse | null) => void;
  disabled: boolean;
  /** The link(s) the reviewer marked above, if any (docs/admin.md 5.3/5.4). */
  range: [number, number] | null;
}

export function PuzzleEditor({
  puzzle,
  edits,
  edges,
  state,
  onChange,
  disabled,
  range,
}: PuzzleEditorProps) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [openDecoy, setOpenDecoy] = useState<string | null>(null);
  const [options, setOptions] = useState<SwapOption[] | null>(null);
  const [linkFixes, setLinkFixes] = useState<LinkFixOption[] | null>(null);
  const [rangeFixes, setRangeFixes] = useState<RangeFixOption[] | null>(null);
  const isSpan = range !== null && range[0] !== range[1];

  const chain = state?.chain ?? puzzle.chain;
  const bank = state?.bank ?? puzzle.bank;
  const currentSolution = state?.solution ?? puzzle.solution;
  const solution = new Set(currentSolution);
  const decoys = bank.filter((w) => !solution.has(w)).sort();

  const apply = async (next: WordEdit[], nextEdges: ManualEdge[] = edges) => {
    setBusy(true);
    setError(null);
    try {
      const result = await previewEdit(puzzle.hash, next, nextEdges);
      onChange(next, nextEdges, result);
      setOpenDecoy(null);
      setOptions(null);
      setLinkFixes(null);
      setRangeFixes(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  /** Replace one word wherever it sits. Blank or unchanged input is a no-op. */
  const rewrite =
    (field: WordEdit['field'], removed: string, index?: number) => (raw: string) => {
      const added = raw.trim().toLowerCase();
      if (added === '' || added === removed) return;
      const edit: WordEdit =
        index === undefined ? { field, removed, added } : { field, removed, added, index };
      void apply([...edits, edit]);
    };

  const assertLink = (index: number) =>
    void apply(edits, [...edges, [chain[index] ?? '', chain[index + 1] ?? '', 2.0]]);

  const openSwaps = async (decoy: string) => {
    if (openDecoy === decoy) {
      setOpenDecoy(null);
      return;
    }
    setOpenDecoy(decoy);
    setOptions(null);
    setBusy(true);
    try {
      setOptions((await fetchSwapOptions(puzzle.hash, decoy, edits, edges)).options);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const suggestLinkFixes = async () => {
    if (range === null) return;
    setLinkFixes(null);
    setBusy(true);
    try {
      setLinkFixes((await fetchLinkFixes(puzzle.hash, range[0], edits, edges)).options);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const suggestRangeFixes = async () => {
    if (range === null) return;
    setRangeFixes(null);
    setBusy(true);
    try {
      setRangeFixes(
        (await fetchRangeFixes(puzzle.hash, range[0], range[1], edits, edges)).options,
      );
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const changes = edits.length + edges.length;

  return (
    <div className="adm-panel">
      <div className="adm-section adm-section--tight">
        <span className="adm-note">Rewrite any word — your judgement decides.</span>
        {changes > 0 && (
          <button
            type="button"
            className="adm-btn adm-btn--quiet"
            disabled={disabled || busy}
            onClick={() => {
              onChange([], [], null);
              setOpenDecoy(null);
              setOptions(null);
              setError(null);
            }}
          >
            Revert
          </button>
        )}
      </div>

      {range !== null && (
        <div className="adm-section adm-section--tight">
          <button
            type="button"
            className="adm-btn adm-btn--quiet"
            disabled={disabled || busy}
            onClick={() => void (isSpan ? suggestRangeFixes() : suggestLinkFixes())}
          >
            {isSpan
              ? `Suggest fixes for ${chain[range[0]]} … ${chain[range[1] + 1]}`
              : `Suggest a fix for ${chain[range[0]]} → ${chain[range[0] + 1]}`}
          </button>
          {!isSpan && linkFixes !== null && linkFixes.length === 0 && (
            <p className="adm-note">Nothing survives the uniqueness check.</p>
          )}
          {isSpan && rangeFixes !== null && rangeFixes.length === 0 && (
            <p className="adm-note">
              Nothing survives the uniqueness check for this span — try a narrower one.
            </p>
          )}
        </div>
      )}

      {!isSpan && range !== null && linkFixes !== null && linkFixes.length > 0 && (
        <div className="adm-tiles">
          {linkFixes.map((fix) => (
            <button
              key={`${fix.index}-${fix.word}`}
              type="button"
              className="adm-btn"
              disabled={disabled || busy}
              title={`${fix.source} — replaces rung ${fix.index + 1}`}
              onClick={() =>
                void apply([
                  ...edits,
                  {
                    field: 'solution',
                    removed: currentSolution[fix.index] ?? '',
                    added: fix.word,
                    index: fix.index,
                  },
                ])
              }
            >
              {fix.word}
            </button>
          ))}
        </div>
      )}

      {isSpan && range !== null && rangeFixes !== null && rangeFixes.length > 0 && (
        <div className="adm-tiles">
          {rangeFixes.map((fix) => (
            <button
              key={`${fix.startIndex}-${fix.words.join('-')}`}
              type="button"
              className="adm-btn"
              disabled={disabled || busy}
              title={`${fix.source} — replaces rungs ${fix.startIndex + 1}-${
                fix.startIndex + fix.words.length
              }`}
              onClick={() =>
                void apply([
                  ...edits,
                  ...fix.words.map((word, offset) => ({
                    field: 'solution' as const,
                    removed: currentSolution[fix.startIndex + offset] ?? '',
                    added: word,
                    index: fix.startIndex + offset,
                  })),
                ])
              }
            >
              {fix.words.join(' → ')}
            </button>
          ))}
        </div>
      )}

      <div className="adm-tiles">
        {chain.map((word, i) => (
          <WordInput
            key={`${i}-${word}`}
            value={word}
            emphasis={i === 0 || i === chain.length - 1}
            disabled={disabled || busy}
            onCommit={
              i === 0
                ? rewrite('start', word)
                : i === chain.length - 1
                  ? rewrite('end', word)
                  : rewrite('solution', word, i - 1)
            }
          />
        ))}
      </div>

      <div className="adm-tiles">
        {decoys.map((word) => (
          <span key={word} className="adm-cluster">
            <WordInput
              value={word}
              disabled={disabled || busy}
              onCommit={rewrite('bank', word)}
            />
            <button
              type="button"
              className="adm-btn adm-btn--quiet adm-btn--tiny"
              disabled={disabled || busy}
              onClick={() => void openSwaps(word)}
              aria-expanded={openDecoy === word}
              aria-label={`Suggest replacements for ${word}`}
              title="Replacements the engine has already proved"
            >
              ⌄
            </button>
          </span>
        ))}
      </div>

      {openDecoy !== null && (
        <div>
          <p className="adm-lead">
            Proved replacements for <em>{openDecoy}</em>:
          </p>
          {options === null && <p className="adm-meta">proving…</p>}
          {options?.length === 0 && (
            <p className="adm-note">Nothing survives the uniqueness check.</p>
          )}
          <div className="adm-tiles">
            {(options ?? []).map((option) => (
              <button
                key={option.word}
                type="button"
                className="adm-btn"
                disabled={disabled || busy}
                title={option.source}
                onClick={() =>
                  void apply([
                    ...edits,
                    { field: 'bank', removed: openDecoy, added: option.word },
                  ])
                }
              >
                {option.word}
              </button>
            ))}
          </div>
        </div>
      )}

      {error !== null && <p className="adm-refusal">{error}</p>}

      {/* A missing rung is a refusal the reviewer can answer, so it arrives
          with the answer attached rather than as prose to act on later. */}
      {(state?.brokenLinks ?? []).map((i) => (
        <div key={`gap-${i}`} className="adm-cluster adm-cluster--gap">
          <span className="adm-refusal">
            No known link between <em>{chain[i]}</em> and <em>{chain[i + 1]}</em>.
          </span>
          <button
            type="button"
            className="adm-btn"
            disabled={disabled || busy}
            onClick={() => assertLink(i)}
          >
            It holds — assert it
          </button>
        </div>
      ))}

      {/* Everything else the machine refuses is arithmetic, not judgement. */}
      {state?.refusals
        .filter((line) => !line.startsWith('no link for'))
        .map((line) => (
          <p key={line} className="adm-refusal">
            {line}
          </p>
        ))}

      {state !== null && state.assertedLinks.length > 0 && (
        <p className="adm-asserted">
          {state.assertedLinks.length === 1
            ? 'One link rests on your word, and ships as evidence.'
            : `${state.assertedLinks.length} links rest on your word, and ship as evidence.`}
        </p>
      )}

      {state?.notes
        .filter((n) => !n.includes('rests on your word'))
        .map((note) => (
          <p key={note} className="adm-note">
            {note}
          </p>
        ))}
    </div>
  );
}

interface WordInputProps {
  value: string;
  onCommit: (value: string) => void;
  disabled: boolean;
  emphasis?: boolean;
}

function WordInput({ value, onCommit, disabled, emphasis }: WordInputProps) {
  const [draft, setDraft] = useState(value);
  // `key` on the caller remounts this when the word changes underneath, so a
  // committed edit shows the new word rather than the stale draft.
  return (
    <input
      className="adm-input adm-input--word"
      value={draft}
      disabled={disabled}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={() => onCommit(draft)}
      onKeyDown={(e) => {
        if (e.key === 'Enter') e.currentTarget.blur();
        if (e.key === 'Escape') setDraft(value);
      }}
      size={Math.max(6, draft.length + (emphasis ? 2 : 1))}
      aria-label={`Rewrite ${value}`}
      style={emphasis ? { fontWeight: 600, textTransform: 'uppercase' } : undefined}
    />
  );
}
