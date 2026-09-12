/**
 * Presentation tier. The visible timer, replacing lives (planning.md 2.5.2).
 *
 * Deliberately visible through the whole game, not just the win screen -- the
 * old hearts meter read as a budget to spend; this reads as a clock running,
 * which is the trade the timer model makes on purpose.
 */

import { HINT_TIME_PENALTY_MS } from '../engine/types';

export interface TimerProps {
  elapsedMs: number;
  /** True for a moment right after a hint is taken, so the penalty is seen landing. */
  hintFlash: boolean;
}

function formatTime(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, '0')}`;
}

export function Timer({ elapsedMs, hintFlash }: TimerProps) {
  return (
    <div
      className="flex items-center gap-1.5 text-base font-medium tabular-nums"
      role="timer"
      aria-label={`Elapsed time ${formatTime(elapsedMs)}`}
    >
      <span aria-hidden="true">{formatTime(elapsedMs)}</span>
      {hintFlash && (
        <span aria-hidden="true" className="animate-pulse text-[13px] font-semibold text-heart">
          +{Math.round(HINT_TIME_PENALTY_MS / 1000)}s
        </span>
      )}
    </div>
  );
}
