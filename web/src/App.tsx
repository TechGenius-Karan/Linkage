/**
 * Presentation tier. Wiring, the four screens, and the effects that touch the
 * outside world (planning.md 8.7).
 *
 * Everything below `<App>` is presentational. Everything App does that is not
 * rendering is here: loading, persisting, and noticing that midnight passed.
 */

import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from 'react';
import { dateForPuzzleNumber, puzzleNumberFor } from './engine/dailyIndex';
import {
  hintsRemaining,
  initialState,
  isBoardFull,
  livesRemaining,
  makeGameReducer,
} from './engine/gameReducer';
import type { ProgressStore, PuzzleRepository } from './engine/ports';
import { recordResult } from './engine/stats';
import { PuzzleNotFound, type GameState, type Puzzle } from './engine/types';
import { AttemptHistory } from './ui/AttemptHistory';
import { Board } from './ui/Board';
import { Header } from './ui/Header';
import { SubmitBar } from './ui/SubmitBar';
import { WordBank } from './ui/WordBank';

type Screen =
  | { kind: 'loading' }
  | { kind: 'ready'; puzzle: Puzzle }
  | { kind: 'missing' }
  | { kind: 'error'; message: string };

/**
 * `?puzzle=N` forces a puzzle number. Development needs it because the epoch is
 * in the future, so "today" resolves to nothing until launch — and after launch
 * it is still the only way to look at a specific day without changing the clock.
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
  store: ProgressStore;
}

export function App({ repo, store }: AppProps) {
  const [screen, setScreen] = useState<Screen>({ kind: 'loading' });
  const [id, setId] = useState(() => requestedPuzzleNumber(new Date()));
  const [newDayAvailable, setNewDayAvailable] = useState(false);

  const load = useCallback(
    (puzzleId: number) => {
      if (puzzleId < 1) {
        setScreen({ kind: 'missing' });
        return;
      }
      setScreen({ kind: 'loading' });
      repo
        .load(puzzleId, dateForPuzzleNumber(puzzleId))
        .then((puzzle) => setScreen({ kind: 'ready', puzzle }))
        .catch((err: unknown) => {
          if (err instanceof PuzzleNotFound) setScreen({ kind: 'missing' });
          else setScreen({ kind: 'error', message: (err as Error).message });
        });
    },
    [repo],
  );

  useEffect(() => load(id), [load, id]);

  /**
   * A tab left open overnight would keep serving yesterday's puzzle and — worse
   * — write progress under the old id. Recompute on wake, then *offer* the new
   * day rather than yanking the board away mid-game (planning.md 8.7).
   */
  useEffect(() => {
    const check = () => {
      if (document.visibilityState === 'hidden') return;
      if (requestedPuzzleNumber(new Date()) !== id) setNewDayAvailable(true);
    };
    document.addEventListener('visibilitychange', check);
    window.addEventListener('focus', check);
    return () => {
      document.removeEventListener('visibilitychange', check);
      window.removeEventListener('focus', check);
    };
  }, [id]);

  return (
    <div className="flex min-h-screen justify-center px-4 pb-11 pt-7">
      <div className="flex w-full max-w-[360px] flex-col gap-6">
        {screen.kind === 'ready' ? (
          <Game
            key={screen.puzzle.id}
            puzzle={screen.puzzle}
            store={store}
            newDayAvailable={newDayAvailable}
            onPlayToday={() => {
              setNewDayAvailable(false);
              setId(requestedPuzzleNumber(new Date()));
            }}
          />
        ) : (
          <>
            <Header puzzleNumber={id} />
            <Placeholder screen={screen} onRetry={() => load(id)} />
          </>
        )}
      </div>
    </div>
  );
}

function Placeholder({ screen, onRetry }: { screen: Screen; onRetry: () => void }) {
  if (screen.kind === 'loading') {
    // The payload is ~1 KB. A skeleton would be more machinery than the thing
    // it stands in for.
    return <p className="py-16 text-center text-[15px] text-ink-muted">Loading…</p>;
  }
  if (screen.kind === 'missing') {
    return (
      <p className="py-16 text-center text-[15px] text-ink-muted">
        No puzzle today. Come back tomorrow.
      </p>
    );
  }
  return (
    <div className="flex flex-col items-center gap-4 py-16">
      <p className="text-center text-[15px] text-ink-muted">Couldn’t load today’s puzzle.</p>
      <button
        type="button"
        className="ring-focus rounded-lg bg-accent px-5 py-3 text-[15px] font-semibold text-ground"
        onClick={onRetry}
      >
        Try again
      </button>
    </div>
  );
}

interface GameProps {
  puzzle: Puzzle;
  store: ProgressStore;
  newDayAvailable: boolean;
  onPlayToday: () => void;
}

function Game({ puzzle, store, newDayAvailable, onPlayToday }: GameProps) {
  const reducer = useMemo(() => makeGameReducer(puzzle), [puzzle]);
  const [state, dispatch] = useReducer(
    reducer,
    puzzle.id,
    (pid) => store.readProgress(pid) ?? initialState(pid),
  );

  // Persist every change. Cheap, and it is what makes a mid-game refresh
  // restore the board and the spent lives exactly.
  useEffect(() => {
    store.writeProgress(state.puzzleId, state);
  }, [store, state]);

  // Fold a finished game into the stats exactly once. `recordResult` is
  // idempotent by puzzle id, so a refresh on the win screen cannot inflate a
  // streak — but the ref keeps it from even trying on every render.
  const recorded = useRef(false);
  useEffect(() => {
    if (state.status === 'playing' || recorded.current) return;
    recorded.current = true;
    store.writeStats(recordResult(store.readStats(), state));
  }, [store, state]);

  const lives = livesRemaining(state);
  const lastAttempt = state.attempts.at(-1);
  const over = state.status !== 'playing';

  return (
    <>
      <Header
        puzzleNumber={puzzle.id}
        onHint={
          over || hintsRemaining(state, puzzle) === 0
            ? undefined
            : () => dispatch({ type: 'TAKE_HINT' })
        }
      />

      {newDayAvailable && (
        <button
          type="button"
          className="ring-focus rounded-lg border border-accent bg-accent-sub px-4 py-2.5 text-[13px] font-medium text-ink"
          onClick={onPlayToday}
        >
          New puzzle available — play today’s
        </button>
      )}

      <Board
        start={puzzle.start}
        end={puzzle.end}
        slots={state.slots}
        revealed={state.status === 'lost' ? puzzle.solution : undefined}
        onSlotClick={over ? undefined : (slot) => dispatch({ type: 'PLACE_TILE', slot })}
        onSlotRemove={over ? undefined : (slot) => dispatch({ type: 'REMOVE_TILE', slot })}
        onMove={over ? undefined : (from, to) => dispatch({ type: 'MOVE_TILE', from, to })}
        onEscape={
          over
            ? undefined
            : () => {
                if (state.selectedTile !== null) {
                  dispatch({ type: 'SELECT_TILE', tileId: state.selectedTile });
                }
              }
        }
      />

      <SubmitBar
        livesRemaining={lives}
        lastCorrect={lastAttempt?.correctCount ?? null}
        status={state.status}
        attemptsTaken={state.attempts.length}
        canSubmit={isBoardFull(state)}
        onSubmit={() => dispatch({ type: 'SUBMIT' })}
      />

      <WordBank
        bank={puzzle.bank}
        // On a loss the board shows the answer, so the bank has to ghost the
        // answer too. Ghosting the player's wrong tiles instead leaves the two
        // halves of the screen disagreeing about what is on the board.
        placed={
          state.status === 'lost'
            ? puzzle.solution
            : state.slots.filter((w): w is string => w !== null)
        }
        selected={state.selectedTile}
        confirmed={state.hintsUsed}
        onTileClick={over ? undefined : (tileId) => dispatch({ type: 'SELECT_TILE', tileId })}
      />

      <AttemptHistory attempts={state.attempts} />
    </>
  );
}

export type { GameState };
