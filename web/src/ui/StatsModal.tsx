/**
 * Presentation tier. Streak, best/average time, and the time distribution
 * (planning.md 8.5.1). No win % — every completed game is a win (2.5.1).
 */

import { TIME_BUCKETS_MS } from '../engine/stats';
import type { Stats } from '../engine/types';
import { Modal } from './Modal';

export interface StatsModalProps {
  open: boolean;
  onClose: () => void;
  stats: Stats;
}

function formatTime(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, '0')}`;
}

/** e.g. 30_000 -> "30s", 120_000 -> "2m". Short form for a narrow chart label. */
function shortDuration(ms: number): string {
  return ms < 60_000 ? `${ms / 1000}s` : `${ms / 60_000}m`;
}

const lastBucketMs = TIME_BUCKETS_MS[TIME_BUCKETS_MS.length - 1]!;
const BUCKET_LABELS = TIME_BUCKETS_MS.map((ms) => `<${shortDuration(ms)}`).concat(
  `${shortDuration(lastBucketMs)}+`,
);

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex flex-col items-center gap-1">
      <span className="font-word text-[22px] font-semibold tabular-nums">{value}</span>
      <span className="text-[11px] text-ink-muted">{label}</span>
    </div>
  );
}

export function StatsModal({ open, onClose, stats }: StatsModalProps) {
  const average =
    stats.gamesPlayed === 0 ? null : Math.round(stats.totalTimeMs / stats.gamesPlayed);
  const max = Math.max(1, ...stats.distribution);

  return (
    <Modal open={open} onClose={onClose}>
      <div className="flex w-[300px] flex-col gap-5 p-6">
        <span className="font-word text-[19px] font-semibold tracking-[0.01em]">Statistics</span>

        <div className="grid grid-cols-4 gap-2 border-b border-rule pb-5">
          <Stat label="Played" value={stats.gamesPlayed} />
          <Stat label="Streak" value={stats.currentStreak} />
          <Stat label="Best streak" value={stats.maxStreak} />
          <Stat label="Best time" value={stats.bestTimeMs === null ? '–' : formatTime(stats.bestTimeMs)} />
        </div>

        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between text-[13px] font-medium text-ink-muted">
            <span>Time distribution</span>
            <span>{average === null ? '' : `avg ${formatTime(average)}`}</span>
          </div>
          {stats.distribution.map((count, i) => (
            <div key={i} className="flex items-center gap-2 text-[13px] text-ink-muted">
              <span className="w-9 shrink-0 tabular-nums">{BUCKET_LABELS[i]}</span>
              <div className="h-4 flex-1 overflow-hidden rounded bg-accent-sub">
                <div
                  className="h-full rounded bg-accent"
                  style={{ width: `${Math.max(4, (count / max) * 100)}%` }}
                />
              </div>
              <span className="w-4 shrink-0 text-right tabular-nums">{count}</span>
            </div>
          ))}
        </div>

        <button
          type="button"
          className="ring-focus min-h-12 rounded-lg border border-rule text-[15px] font-semibold text-ink-muted"
          onClick={onClose}
        >
          Close
        </button>
      </div>
    </Modal>
  );
}
