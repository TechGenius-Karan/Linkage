/**
 * Presentation tier. Wiring and the four screens (planning.md 8.7).
 *
 * Phase 3 renders a real puzzle and nothing else — no reducer, no placement,
 * no persistence. The handlers below are deliberately absent rather than
 * stubbed, so a button that does nothing renders as disabled instead of
 * pretending to work.
 */

import { useCallback, useEffect, useState } from 'react';
import type { PuzzleRepository } from './engine/ports';
import { dateForPuzzleNumber, puzzleNumberFor } from './engine/dailyIndex';
import { CHAIN_LENGTH, PuzzleNotFound, type Puzzle } from './engine/types';
import { Board } from './ui/Board';
import { Header } from './ui/Header';
import { WordBank } from './ui/WordBank';

type Screen =
  | { kind: 'loading' }
  | { kind: 'ready'; puzzle: Puzzle }
  | { kind: 'missing' }
  | { kind: 'error'; message: string };

/**
 * `?puzzle=N` forces a puzzle number. Development needs this because the epoch
 * is in the future, so "today" resolves to nothing until launch — and after
 * launch it is still the only way to look at a specific day without changing
 * the system clock.
 */
function requestedPuzzleNumber(now: Date): number {
  const override = new URLSearchParams(window.location.search).get('puzzle');
  if (override !== null) {
    const n = Number(override);
    if (Number.isInteger(n) && n >= 1) return n;
  }
  return puzzleNumberFor(now);
}

export interface AppProps {
  repo: PuzzleRepository;
}

export function App({ repo }: AppProps) {
  const [screen, setScreen] = useState<Screen>({ kind: 'loading' });
  const id = requestedPuzzleNumber(new Date());

  const load = useCallback(() => {
    // Before the epoch there is no puzzle to ask for, and asking would 404
    // once per visitor for no reason.
    if (id < 1) {
      setScreen({ kind: 'missing' });
      return;
    }
    setScreen({ kind: 'loading' });
    repo
      .load(id, dateForPuzzleNumber(id))
      .then((puzzle) => setScreen({ kind: 'ready', puzzle }))
      .catch((err: unknown) => {
        // A missing puzzle and a broken network are different states and want
        // different screens — one is final, the other is worth retrying.
        if (err instanceof PuzzleNotFound) setScreen({ kind: 'missing' });
        else setScreen({ kind: 'error', message: (err as Error).message });
      });
  }, [repo, id]);

  useEffect(load, [load]);

  return (
    <div className="flex min-h-screen justify-center px-4 pb-11 pt-7">
      <div className="flex w-full max-w-[360px] flex-col gap-6">
        <Header puzzleNumber={id} />
        <Screen screen={screen} onRetry={load} />
      </div>
    </div>
  );
}

function Screen({ screen, onRetry }: { screen: Screen; onRetry: () => void }) {
  switch (screen.kind) {
    case 'loading':
      // The payload is ~1 KB, so this is on screen for a frame or two. A
      // skeleton would be more machinery than the thing it stands in for.
      return <p className="py-16 text-center text-[15px] text-ink-muted">Loading…</p>;

    case 'missing':
      return (
        <p className="py-16 text-center text-[15px] text-ink-muted">
          No puzzle today. Come back tomorrow.
        </p>
      );

    case 'error':
      return (
        <div className="flex flex-col items-center gap-4 py-16">
          <p className="text-center text-[15px] text-ink-muted">
            Couldn’t load today’s puzzle.
          </p>
          <button
            type="button"
            className="ring-focus rounded-lg bg-accent px-5 py-3 text-[15px] font-semibold text-ground"
            onClick={onRetry}
          >
            Try again
          </button>
        </div>
      );

    case 'ready': {
      const { puzzle } = screen;
      return (
        <>
          <Board
            start={puzzle.start}
            end={puzzle.end}
            slots={Array<string | null>(CHAIN_LENGTH).fill(null)}
          />
          <WordBank bank={puzzle.bank} placed={[]} selected={null} />
        </>
      );
    }
  }
}
