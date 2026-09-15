/**
 * Presentation tier. Streak, best/average time, and the time distribution
 * (planning.md 8.5.1). No win % — every completed game is a win (2.5.1).
 */

import { TIME_BUCKETS_MS } from '../engine/stats';
import type { Stats } from '../engine/types';
import { FireIcon } from './icons';
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

function StatCard({
  value,
  label,
  accent = false,
}: {
  value: string;
  label: string;
  accent?: boolean;
}) {
  return (
    <div className="flex flex-col gap-0.5 rounded-2xl bg-ground px-[15px] py-[14px]">
      <span
        className={`font-data text-[27px] font-semibold leading-[1.1] tracking-[-0.03em] ${accent ? 'text-accent' : 'text-ink'}`}
      >
        {value}
      </span>
      <span className="text-[12px] font-semibold tracking-[0.01em] text-ink-muted">{label}</span>
    </div>
  );
}

export function StatsModal({ open, onClose, stats }: StatsModalProps) {
  const average =
    stats.gamesPlayed === 0 ? null : Math.round(stats.totalTimeMs / stats.gamesPlayed);
  const hasSolves = stats.gamesPlayed > 0;
  const max = Math.max(1, ...stats.distribution);
  const best = stats.distribution.indexOf(Math.max(...stats.distribution));

  return (
    <Modal open={open} onClose={onClose}>
      <div className="w-[340px] px-6 pb-[22px] pt-[26px]">
        <div className="flex items-start justify-between gap-3">
          <div className="flex flex-col gap-[5px]">
            <span className="font-word text-[27px] font-semibold leading-[1.05] tracking-[-0.015em]">
              Statistics
            </span>
            <span className="text-[12px] font-semibold tracking-[0.14em] text-accent">
              LINKAGE &middot; ALL TIME
            </span>
          </div>
          <button
            type="button"
            className="ring-focus grid h-8 w-8 flex-none place-items-center rounded-full bg-ground text-ink-muted transition-colors hover:text-ink"
            aria-label="Close"
            onClick={onClose}
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              aria-hidden="true"
            >
              <line x1="6" y1="6" x2="18" y2="18" />
              <line x1="18" y1="6" x2="6" y2="18" />
            </svg>
          </button>
        </div>

        <div className="mt-5 mb-[18px] h-px bg-rule" />

        <div className="grid grid-cols-2 gap-2.5">
          <StatCard value={String(stats.gamesPlayed)} label="Played" />
          <StatCard value={String(stats.currentStreak)} label="Current streak" accent />
          <StatCard
            value={stats.bestTimeMs === null ? '—' : formatTime(stats.bestTimeMs)}
            label="Best time"
          />
          <StatCard
            value={average === null ? '—' : formatTime(average)}
            label="Average time"
          />
        </div>

        <div className="mt-[22px] mb-3 flex items-baseline justify-between">
          <span className="text-[11.5px] font-bold tracking-[0.14em] text-ink-muted">
            SOLVE TIMES
          </span>
          <span className="text-[11.5px] font-semibold text-ink-muted">
            {hasSolves ? `${stats.gamesPlayed} solves` : 'no solves yet'}
          </span>
        </div>

        <div className="flex flex-col gap-[7px]">
          {stats.distribution.map((count, i) => {
            const isBest = hasSolves && count > 0 && i === best;
            const barColor = count === 0 ? 'bg-rule' : isBest ? 'bg-accent' : 'bg-accent-sub';
            const width = count === 0 ? '4px' : `${Math.round(14 + (count / max) * 86)}%`;
            return (
              <div key={i} className="flex items-center gap-2.5">
                <span className="w-[38px] flex-none text-right font-data text-[11.5px] font-medium text-ink-muted">
                  {BUCKET_LABELS[i]}
                </span>
                <div className="h-5 flex-1 overflow-hidden rounded-[7px] bg-ground">
                  <div className={`h-full rounded-[7px] ${barColor}`} style={{ width }} />
                </div>
                <span
                  className={`w-4 flex-none text-right font-data text-[11.5px] font-semibold ${isBest ? 'text-accent' : 'text-ink-muted'}`}
                >
                  {count}
                </span>
              </div>
            );
          })}
        </div>

        <div className="mt-5 mb-3.5 h-px bg-rule" />

        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="text-accent">
              <FireIcon size={19} />
            </span>
            <span className="text-[13px] font-semibold text-ink-muted">
              {hasSolves ? 'Best streak' : 'Play today to start a streak'}
            </span>
          </div>
          <span className="font-data text-[13px] font-semibold text-ink">
            {hasSolves ? `${stats.maxStreak} day${stats.maxStreak === 1 ? '' : 's'}` : '—'}
          </span>
        </div>

        <button
          type="button"
          className="ring-focus mt-[18px] h-[50px] w-full rounded-[15px] bg-accent text-[15.5px] font-bold tracking-[0.005em] text-ground transition-[filter,transform] hover:brightness-[1.07] active:scale-[0.99]"
          onClick={onClose}
        >
          Close
        </button>
      </div>
    </Modal>
  );
}
