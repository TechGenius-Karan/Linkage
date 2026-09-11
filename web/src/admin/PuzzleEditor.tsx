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
 * than a matter of taste, and getting it wrong means a player arranges the
 * board correctly and is told they are wrong.
 *
 * Nothing here is saved. Edits live in component state until the puzzle is
 * approved, which is why the state machine has four states and not five.
 */

import { useState } from 'react';
import {
  fetchSwapOptions,
  previewEdit,
  type EditResponse,
  type ManualEdge,
  type QueuePuzzle,
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
}

export function PuzzleEditor({
  puzzle,
  edits,
  edges,
  state,
  onChange,
  disabled,
}: PuzzleEditorProps) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [openDecoy, setOpenDecoy] = useState<string | null>(null);
  const [options, setOptions] = useState<SwapOption[] | null>(null);

  const chain = state?.chain ?? puzzle.chain;
  const bank = state?.bank ?? puzzle.bank;
  const solution = new Set(state?.solution ?? puzzle.solution);
  const decoys = bank.filter((w) => !solution.has(w)).sort();

  const apply = async (next: WordEdit[], nextEdges: ManualEdge[] = edges) => {
    setBusy(true);
    setError(null);
    try {
      const result = await previewEdit(puzzle.hash, next, nextEdges);
      onChange(next, nextEdges, result);
      setOpenDecoy(null);
      setOptions(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  /** Replace one word wherever it sits. Blank or unchanged input is a no-op. */
  const rewrite = (field: WordEdit['field'], removed: string, index?: number) =>
    (raw: string) => {
      const added = raw.trim().toLowerCase();
      if (added === '' || added === removed) return;
      const edit: WordEdit = index === undefined
        ? { field, removed, added }
        : { field, removed, added, index };
      void apply([...edits, edit]);
    };

  const assert = (index: number) => {
    const pair: ManualEdge = [chain[index] ?? '', chain[index + 1] ?? '', 2.0];
    void apply(edits, [...edges, pair]);
  };

  const revert = () => {
    onChange([], [], null);
    setOpenDecoy(null);
    setOptions(null);
    setError(null);
  };

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

  const touched = edits.length > 0 || edges.length > 0;

  return (
    <div className="flex flex-col gap-2.5 rounded-lg border border-rule bg-ground p-3">
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-xs font-medium text-ink-muted">
          Rewrite any word. Your judgement decides whether it reads.
        </span>
        {touched && (
          <button
            type="button"
            disabled={disabled || busy}
            onClick={revert}
            className="ring-focus rounded px-1.5 py-0.5 text-xs underline disabled:opacity-40"
          >
            Revert {edits.length + edges.length} change
            {edits.length + edges.length === 1 ? '' : 's'}
          </button>
        )}
      </div>

      {/* The chain: six editable slots, endpoints included. */}
      <div className="flex flex-wrap items-center gap-1">
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

      {/* Decoys: editable too, and each opens the proved-safe menu. */}
      <div>
        <div className="mb-1 text-xs text-ink-muted">Decoys ({decoys.length})</div>
        <div className="flex flex-wrap items-center gap-1">
          {decoys.map((word) => (
            <span key={word} className="flex items-center">
              <WordInput
                value={word}
                disabled={disabled || busy}
                onCommit={rewrite('bank', word)}
                small
              />
              <button
                type="button"
                disabled={disabled || busy}
                onClick={() => void openSwaps(word)}
                aria-expanded={openDecoy === word}
                aria-label={`Suggest replacements for ${word}`}
                title="Replacements the engine has already proved"
                className="ring-focus -ml-0.5 rounded px-1 text-xs text-ink-muted hover:text-ink disabled:opacity-40"
              >
                ⌄
              </button>
            </span>
          ))}
        </div>
      </div>

      {openDecoy !== null && (
        <div className="rounded-md border border-rule bg-surface p-2">
          <p className="mb-1 text-xs text-ink-muted">
            Proved replacements for <span className="font-word">{openDecoy}</span> — the number
            is how tempting the generator rates it, so lower is an easier bank.
          </p>
          {options === null && <p className="text-xs text-ink-muted">Proving…</p>}
          {options?.length === 0 && (
            <p className="text-xs text-ink-muted">
              Nothing survives the uniqueness check. This bank is as loose as it gets.
            </p>
          )}
          <div className="flex flex-wrap gap-1">
            {(options ?? []).map((option) => (
              <button
                key={option.word}
                type="button"
                disabled={disabled || busy}
                title={option.source}
                onClick={() =>
                  void apply([...edits, { field: 'bank', removed: openDecoy, added: option.word }])
                }
                className="ring-focus rounded border border-rule px-1.5 py-0.5 text-[13px] hover:bg-accent-sub disabled:opacity-40"
              >
                <span className="font-word">{option.word}</span>
                <span className="ml-1 font-data text-[10px] text-ink-muted">
                  {option.temptingness.toFixed(1)}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}

      {error !== null && <p className="text-xs text-heart">{error}</p>}

      {/* A missing rung is a refusal the reviewer can answer, so it arrives
          with the answer attached rather than as prose to act on later. */}
      {(state?.brokenLinks ?? []).map((i) => (
        <div key={`gap-${i}`} className="flex flex-wrap items-center gap-2 text-xs">
          <span className="text-heart">
            ConceptNet has no link for{' '}
            <span className="font-word">
              {chain[i]} → {chain[i + 1]}
            </span>
            .
          </span>
          <button
            type="button"
            disabled={disabled || busy}
            onClick={() => assert(i)}
            className="ring-focus rounded border border-accent px-1.5 py-0.5 font-medium text-accent disabled:opacity-40"
          >
            It holds — assert it
          </button>
        </div>
      ))}

      {/* Everything else the machine refuses is arithmetic, not judgement. */}
      {state?.refusals
        .filter((line) => !line.startsWith('no link for'))
        .map((line) => (
          <p key={line} className="text-xs font-medium text-heart">
            Refused — {line}
          </p>
        ))}

      {state !== null && state.assertedLinks.length > 0 && (
        <p className="text-xs text-accent">
          {state.assertedLinks.length === 1
            ? '1 rung rests on your word'
            : `${state.assertedLinks.length} rungs rest on your word`}
          . {state.assertedLinks.length === 1 ? 'It ships' : 'They ship'} with the puzzle as
          evidence.
        </p>
      )}

      {state?.notes
        .filter((n) => !n.includes('rests on your word'))
        .map((note) => (
          <p key={note} className="text-xs text-ink-muted">
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
  small?: boolean;
}

function WordInput({ value, onCommit, disabled, emphasis, small }: WordInputProps) {
  const [draft, setDraft] = useState(value);
  // `key` on the caller remounts this when the word changes underneath, so a
  // committed edit shows the new word rather than the stale draft.
  return (
    <input
      value={draft}
      disabled={disabled}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={() => onCommit(draft)}
      onKeyDown={(e) => {
        if (e.key === 'Enter') e.currentTarget.blur();
        if (e.key === 'Escape') setDraft(value);
      }}
      size={Math.max(6, draft.length + (emphasis ? 3 : 1))}
      aria-label={`Rewrite ${value}`}
      className={`ring-focus rounded border border-rule bg-surface px-1.5 py-0.5 font-word disabled:opacity-40 ${
        small ? 'text-[13px]' : 'text-[15px]'
      } ${emphasis ? 'font-semibold uppercase' : ''}`}
    />
  );
}
