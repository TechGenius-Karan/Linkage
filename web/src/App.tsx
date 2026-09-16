/**
 * Presentation tier. Wiring, the four screens, and the effects that touch the
 * outside world (planning.md 8.7).
 *
 * Everything below `<App>` is presentational. Everything App does that is not
 * rendering is here: loading, persisting, and noticing that midnight passed.
 */

import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from 'react';
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from '@dnd-kit/core';
import { todayIsoDate } from './engine/dailyIndex';
import {
  elapsedMs,
  hintsRemaining,
  initialState,
  isBoardFull,
  makeGameReducer,
} from './engine/gameReducer';
import type { ProgressStore, PuzzleRepository } from './engine/ports';
import { buildShareParts, buildShareText } from './engine/shareText';
import { recordResult } from './engine/stats';
import { PuzzleNotFound, type GameState, type Puzzle } from './engine/types';
import { Board } from './ui/Board';
import {
  BANK_DROPPABLE_ID,
  DRAG_ACTIVATION_DISTANCE_PX,
  parseSlotDroppableId,
  type DragOrigin,
} from './ui/dnd';
import { Header } from './ui/Header';
import { HowToPlayModal } from './ui/HowToPlayModal';
import { RestingMoonIcon } from './ui/icons';
import { SettingsModal } from './ui/SettingsModal';
import { StatsModal } from './ui/StatsModal';
import { SubmitBar } from './ui/SubmitBar';
import { Timer } from './ui/Timer';
import { WordBank } from './ui/WordBank';

type Panel = 'stats' | 'howto' | 'settings' | null;

type Screen =
  | { kind: 'loading' }
  | { kind: 'ready'; puzzle: Puzzle }
  | { kind: 'missing' }
  | { kind: 'error'; message: string };

/**
 * `?date=YYYY-MM-DD` forces a specific day. Development needs it to look at a
 * puzzle without changing the system clock — and since the archive can skip a
 * day (planning.md 3.3), a puzzle *number* would not reliably name one date.
 */
function requestedDate(now: Date): string {
  const override = new URLSearchParams(window.location.search).get('date');
  if (override !== null && /^\d{4}-\d{2}-\d{2}$/.test(override)) return override;
  return todayIsoDate(now);
}

export interface AppProps {
  repo: PuzzleRepository;
  store: ProgressStore;
}

export function App({ repo, store }: AppProps) {
  const [screen, setScreen] = useState<Screen>({ kind: 'loading' });
  const [date, setDate] = useState(() => requestedDate(new Date()));
  const [newDayAvailable, setNewDayAvailable] = useState(false);
  // Lives here, not inside Game: settings/stats/how-to-play don't need a
  // loaded puzzle (SettingsModal is pure theme, HowToPlayModal is static
  // rules, StatsModal reads store.readStats() directly), so the icons that
  // open them must work on the loading/missing/error screens too.
  const [panel, setPanel] = useState<Panel>(null);

  // Gates `Game` itself, not just its content -- Linkage is timed, so the
  // fix for "a new player doesn't know the rules yet" has to be "the clock
  // hasn't started yet," not "the rules are shown over a clock that has."
  // `Game`'s `useReducer` captures `Date.now()` at mount, so simply not
  // mounting it yet is the whole mechanism; nothing in gameReducer changes.
  // The gate itself is just HowToPlayModal forced open with `firstRun` --
  // no separate welcome screen, so there is exactly one rules panel to keep
  // in sync rather than two (2026-09-16 chat design).
  const [onboarded, setOnboarded] = useState(() => store.hasOnboarded());
  const dismissGate = useCallback(() => {
    store.markOnboarded();
    setOnboarded(true);
  }, [store]);

  const load = useCallback(
    (day: string) => {
      setScreen({ kind: 'loading' });
      repo
        .load(day)
        .then((puzzle) => setScreen({ kind: 'ready', puzzle }))
        .catch((err: unknown) => {
          if (err instanceof PuzzleNotFound) setScreen({ kind: 'missing' });
          else setScreen({ kind: 'error', message: (err as Error).message });
        });
    },
    [repo],
  );

  useEffect(() => load(date), [load, date]);

  /**
   * A tab left open overnight would keep serving yesterday's puzzle and — worse
   * — write progress under the old id. Recompute on wake, then *offer* the new
   * day rather than yanking the board away mid-game (planning.md 8.7).
   */
  useEffect(() => {
    const check = () => {
      if (document.visibilityState === 'hidden') return;
      if (requestedDate(new Date()) !== date) setNewDayAvailable(true);
    };
    document.addEventListener('visibilitychange', check);
    window.addEventListener('focus', check);
    return () => {
      document.removeEventListener('visibilitychange', check);
      window.removeEventListener('focus', check);
    };
  }, [date]);

  return (
    <div className="flex min-h-screen justify-center px-4 pb-6 pt-4 md:items-center md:py-10">
      {/* Bare on a phone, where the viewport already is the frame. From
          tablet width up, a bordered card with a soft shadow reads as "this
          is the play area" against an otherwise-empty desktop background.
          390px is a common phone logical width (iPhone 12-15); `md:items-center`
          stops the card stretching to fill the browser window's full height,
          so it sizes to its content like an actual phone screen would. */}
      <main className="flex w-full max-w-[390px] flex-col gap-3 md:rounded-[32px] md:border md:border-rule md:bg-surface md:p-6 md:shadow-[0_8px_30px_rgba(31,29,26,0.08)]">
        {/* Nothing to show behind the forced-open modal below -- Settings/Stats
            icons would race it into a second stacked <dialog> if they were
            live here, and the native ::backdrop already covers the viewport. */}
        {!onboarded ? null : screen.kind === 'ready' ? (
          <Game
            key={screen.puzzle.id}
            puzzle={screen.puzzle}
            store={store}
            newDayAvailable={newDayAvailable}
            onPlayToday={() => {
              setNewDayAvailable(false);
              setDate(requestedDate(new Date()));
            }}
            setPanel={setPanel}
          />
        ) : (
          <>
            <Header
              puzzleNumber={null}
              onStats={() => setPanel('stats')}
              onHowToPlay={() => setPanel('howto')}
              onSettings={() => setPanel('settings')}
            />
            <Placeholder screen={screen} onRetry={() => load(date)} />
          </>
        )}
      </main>

      <StatsModal open={panel === 'stats'} onClose={() => setPanel(null)} stats={store.readStats()} />
      <HowToPlayModal
        open={panel === 'howto' || !onboarded}
        firstRun={!onboarded}
        onClose={() => {
          setPanel(null);
          // On a first run, this modal *is* the gate (forced open above) --
          // closing it via the button, the X, Escape, or the backdrop are
          // all "I'm ready," not just a rules dismissal.
          if (!onboarded) dismissGate();
        }}
      />
      <SettingsModal open={panel === 'settings'} onClose={() => setPanel(null)} />
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
      <div className="flex flex-col items-center gap-3 py-14 text-center">
        <span className="relative grid place-items-center">
          <span aria-hidden="true" className="moon-halo" />
          <RestingMoonIcon className="moon-glow" />
        </span>
        {/* Deliberately not `font-word` (the serif used for the wordmark and
            in-game words) -- that read too formal for a line whose whole job
            is to be a light, comforting aside. A system handwriting-style
            stack keeps it playful without pulling in a webfont. */}
        <p
          className="text-[18px] font-semibold text-ink"
          style={{ fontFamily: "'Segoe Print', 'Chalkboard SE', 'Comic Sans MS', cursive" }}
        >
          Today&rsquo;s chain hasn&rsquo;t been forged yet.
        </p>
        <p className="max-w-[240px] text-[14px] text-ink-muted">
          Linkage rests overnight. Come back tomorrow and pick the links back up.
        </p>
      </div>
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
  setPanel: (panel: Panel) => void;
}

function Game({ puzzle, store, newDayAvailable, onPlayToday, setPanel }: GameProps) {
  const reducer = useMemo(() => makeGameReducer(puzzle), [puzzle]);
  const [state, dispatch] = useReducer(
    reducer,
    puzzle.id,
    (pid) => {
      const loaded = store.readProgress(pid) ?? initialState(pid, Date.now());
      // A pause only ever clears via the 'visible' visibilitychange
      // *transition* below -- and a fresh mount (page reload after the
      // browser fully discarded a backgrounded tab, which is exactly when a
      // long pause is most likely) is already visible, so that transition
      // never fires. Without this, a persisted pausedAt would freeze
      // elapsedMs forever. The page is visible right now by definition (it
      // just mounted), so folding the pause in immediately is always correct.
      return loaded.pausedAt !== null ? reducer(loaded, { type: 'RESUME', now: Date.now() }) : loaded;
    },
  );

  // Persist every change. Cheap, and it is what makes a mid-game refresh
  // restore the board and the running timer exactly (planning.md 2.5.2).
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

  // The clock. Ticks once a second while playing; `elapsedMs` freezes itself
  // once `pausedAt`/`finishedAt` are set, so nothing here needs to know why.
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (state.status !== 'playing') return;
    const id = setInterval(() => setNow(Date.now()), 1_000);
    return () => clearInterval(id);
  }, [state.status]);

  // Commute, queue, phone down mid-puzzle (planning.md 2.5.2): the timer must
  // not charge a player for the game being backgrounded.
  useEffect(() => {
    if (state.status !== 'playing') return;
    const onVisibilityChange = () => {
      dispatch({
        type: document.visibilityState === 'hidden' ? 'PAUSE' : 'RESUME',
        now: Date.now(),
      });
    };
    document.addEventListener('visibilitychange', onVisibilityChange);
    return () => document.removeEventListener('visibilitychange', onVisibilityChange);
  }, [state.status]);

  // A hint lands as a visible +20s jump, not just a bigger number on the next
  // tick (planning.md 2.5.3).
  const [hintFlash, setHintFlash] = useState(false);
  const takeHint = useCallback(() => {
    dispatch({ type: 'TAKE_HINT' });
    setHintFlash(true);
    setTimeout(() => setHintFlash(false), 1_500);
  }, []);

  const elapsed = elapsedMs(state, now);
  const lastAttempt = state.attempts.at(-1);
  const over = state.status !== 'playing';

  // Pointer-drag, bank <-> board. `<Board>` and `<WordBank>` are siblings, so
  // this is the one place that sees both a drag's origin and where it
  // landed (same reasoning the old hand-rolled Board.tsx drag used, just one
  // level higher now that dragging crosses between them). `sensors` uses
  // only `PointerSensor` -- mouse, touch and pen are already unified there,
  // same reason the previous implementation gave for skipping a library
  // until now. `activationConstraint.distance` is the tap-vs-drag threshold;
  // under it, the browser's native `click`/`dblclick` fire exactly as before.
  const [activeDrag, setActiveDrag] = useState<DragOrigin | null>(null);
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: DRAG_ACTIVATION_DISTANCE_PX } }),
  );

  const handleDragStart = useCallback((event: DragStartEvent) => {
    setActiveDrag((event.active.data.current as DragOrigin | undefined) ?? null);
  }, []);

  const handleDragCancel = useCallback(() => setActiveDrag(null), []);

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      setActiveDrag(null);
      const origin = event.active.data.current as DragOrigin | undefined;
      const overId = event.over?.id;
      // Released over nothing droppable -- dnd-kit already animates the
      // overlay back to where the drag started; nothing to dispatch means
      // nothing changes underneath it.
      if (origin === undefined || overId === undefined) return;

      if (overId === BANK_DROPPABLE_ID) {
        // A slot's tile dragged to the bank goes back, same as double-tap.
        // A bank tile dragged back onto the bank never left -- no-op.
        if (origin.origin === 'slot') dispatch({ type: 'REMOVE_TILE', slot: origin.index });
        return;
      }

      const slotIndex = parseSlotDroppableId(String(overId));
      if (slotIndex === null) return;

      if (origin.origin === 'bank') {
        // SELECT_TILE toggles -- only select if this word isn't already the
        // held tile, or the second dispatch below would see it deselected.
        if (state.selectedTile !== origin.word) {
          dispatch({ type: 'SELECT_TILE', tileId: origin.word });
        }
        dispatch({ type: 'PLACE_TILE', slot: slotIndex });
      } else if (slotIndex !== origin.index) {
        dispatch({ type: 'MOVE_TILE', from: origin.index, to: slotIndex });
      }
    },
    [state.selectedTile],
  );

  const dragLabel =
    activeDrag === null
      ? null
      : activeDrag.origin === 'bank'
        ? activeDrag.word
        : state.slots[activeDrag.index];

  return (
    // Always wired, not gated on `over`: every draggable already carries its
    // own `disabled={over}` (Board/WordBank below), so a finished game simply
    // never has anything for a sensor to pick up.
    <DndContext
      sensors={sensors}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
      onDragCancel={handleDragCancel}
    >
      <Header
        puzzleNumber={puzzle.id}
        onStats={() => setPanel('stats')}
        onHowToPlay={() => setPanel('howto')}
        onSettings={() => setPanel('settings')}
      />

      {/* The capsule's own padding adds ~12px of height; pull it back out of
          the surrounding gap-6 so the pill outline doesn't grow the page. */}
      <div className="-my-1.5 flex justify-end pr-0.5">
        <Timer elapsedMs={elapsed} hintFlash={hintFlash} />
      </div>

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
        onSlotClick={over ? undefined : (slot) => dispatch({ type: 'PLACE_TILE', slot })}
        onSlotRemove={over ? undefined : (slot) => dispatch({ type: 'REMOVE_TILE', slot })}
        onNudge={over ? undefined : (from, to) => dispatch({ type: 'MOVE_TILE', from, to })}
        onEscape={
          over
            ? undefined
            : () => {
                if (state.selectedTile !== null) {
                  dispatch({ type: 'SELECT_TILE', tileId: state.selectedTile });
                }
              }
        }
        disabled={over}
      />

      <SubmitBar
        lastCorrect={lastAttempt?.correctCount ?? null}
        status={state.status}
        attemptsTaken={state.attempts.length}
        canSubmit={isBoardFull(state)}
        onSubmit={() => dispatch({ type: 'SUBMIT', now: Date.now() })}
        hintsRemaining={hintsRemaining(state, puzzle)}
        onHint={over || hintsRemaining(state, puzzle) === 0 ? undefined : takeHint}
        shareText={state.status === 'won' ? buildShareText(state) : undefined}
        shareParts={state.status === 'won' ? buildShareParts(state) : undefined}
      />

      <WordBank
        bank={puzzle.bank}
        placed={state.slots.filter((w): w is string => w !== null)}
        selected={state.selectedTile}
        confirmed={state.hintsUsed}
        onTileClick={over ? undefined : (tileId) => dispatch({ type: 'SELECT_TILE', tileId })}
        disabled={over}
      />

      <DragOverlay>
        {dragLabel === null ? null : <div className="tile pointer-events-none">{dragLabel}</div>}
      </DragOverlay>
    </DndContext>
  );
}

export type { GameState };
