/**
 * Refining a bank, with the engine holding a veto (planning.md 16.4).
 *
 * Round 1's second finding was that banks came out uniformly too hard — 95% of
 * every bank was a decoy wired to one side of a solution slot. `DISTRACTOR_MIX`
 * fixes that in generation; this fixes the ones that still slip through.
 *
 * Two things make it safe to hand a person this control. The replacements
 * offered are only ones the engine has already proved, so the menu never leads
 * anywhere refused. And the swap itself is re-proved on the way in, so a word
 * that would give the puzzle a second valid solution comes back as a refusal
 * with the reason — the reviewer cannot break uniqueness, even deliberately.
 *
 * Nothing here is saved. Edits live in component state until the puzzle is
 * approved, which is why the state machine still has three states and not four.
 */

import { useState } from 'react';
import { fetchSwapOptions, previewSwap, type BankEdit, type SwapOption } from './adminClient';

export interface BankEditorProps {
  hash: string;
  /** The generated bank, before any edit. */
  bank: string[];
  solution: string[];
  edits: BankEdit[];
  onChange: (edits: BankEdit[]) => void;
  disabled: boolean;
}

export function BankEditor({ hash, bank, solution, edits, onChange, disabled }: BankEditorProps) {
  const [open, setOpen] = useState<string | null>(null);
  const [options, setOptions] = useState<SwapOption[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [refusal, setRefusal] = useState<string | null>(null);

  const answers = new Set(solution);
  // Replay the edits locally so the chips update the instant one is applied.
  const current = bank.map((word) => {
    let showing = word;
    for (const edit of edits) if (edit.removed === showing) showing = edit.added;
    return showing;
  });
  const added = new Set(edits.map((e) => e.added));
  const decoys = current.filter((word) => !answers.has(word)).sort();

  const choose = async (decoy: string) => {
    if (open === decoy) {
      setOpen(null);
      return;
    }
    setOpen(decoy);
    setOptions(null);
    setRefusal(null);
    setBusy(true);
    try {
      setOptions((await fetchSwapOptions(hash, decoy, edits)).options);
    } catch (err) {
      setRefusal((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const apply = async (removed: string, addedWord: string) => {
    const next = [...edits, { removed, added: addedWord }];
    setBusy(true);
    setRefusal(null);
    try {
      // Proved server-side before it reaches component state, so a refusal can
      // never leave the UI showing a bank the engine would not accept.
      await previewSwap(hash, next);
      onChange(next);
      setOpen(null);
      setOptions(null);
    } catch (err) {
      setRefusal((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between gap-3">
        <span className="text-xs font-medium text-ink-muted">Decoys ({decoys.length})</span>
        {edits.length > 0 && (
          <button
            type="button"
            disabled={disabled || busy}
            onClick={() => {
              onChange([]);
              setOpen(null);
              setOptions(null);
              setRefusal(null);
            }}
            className="ring-focus rounded-md px-1.5 py-0.5 text-xs underline disabled:opacity-40"
          >
            Revert {edits.length} swap{edits.length === 1 ? '' : 's'}
          </button>
        )}
      </div>

      <div className="flex flex-wrap gap-1.5">
        {decoys.map((word) => (
          <button
            key={word}
            type="button"
            disabled={disabled || busy}
            onClick={() => void choose(word)}
            aria-expanded={open === word}
            aria-label={`Swap the decoy ${word}`}
            className={`ring-focus rounded-md border px-2 py-1 font-word text-[13px] disabled:opacity-40 ${
              open === word
                ? 'border-accent bg-accent-sub'
                : added.has(word)
                  ? 'border-accent border-dashed'
                  : 'border-rule hover:bg-accent-sub'
            }`}
          >
            {word}
          </button>
        ))}
      </div>

      {refusal !== null && (
        <p className="mt-2 text-xs text-heart">
          Refused: {refusal}
        </p>
      )}

      {open !== null && (
        <div className="mt-2 rounded-lg border border-rule bg-ground p-2.5">
          <p className="mb-1.5 text-xs text-ink-muted">
            Replace <span className="font-word">{open}</span> with — the number is how tempting
            the generator rates it, so a lower one is an easier bank.
          </p>
          {busy && options === null && <p className="text-xs text-ink-muted">Proving options…</p>}
          {options !== null && options.length === 0 && (
            <p className="text-xs text-ink-muted">
              No replacement survives the uniqueness check. This bank is as loose as it gets.
            </p>
          )}
          <div className="flex flex-wrap gap-1.5">
            {(options ?? []).map((option) => (
              <button
                key={option.word}
                type="button"
                disabled={disabled || busy}
                onClick={() => void apply(open, option.word)}
                title={option.source}
                className="ring-focus rounded-md border border-rule bg-surface px-2 py-1 text-[13px] disabled:opacity-40 hover:bg-accent-sub"
              >
                <span className="font-word">{option.word}</span>
                <span className="ml-1.5 text-xs text-ink-muted">{option.temptingness.toFixed(1)}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {edits.length > 0 && (
        <ul className="mt-2 text-xs text-ink-muted">
          {edits.map((edit) => (
            <li key={`${edit.removed}-${edit.added}`} className="font-word">
              {edit.removed} → {edit.added}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
