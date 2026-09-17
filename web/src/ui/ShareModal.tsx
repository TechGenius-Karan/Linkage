/**
 * Presentation tier. The win panel: celebration, today's stats, and the share
 * card (planning.md 2.7). Opens by itself the moment a game is won — it *is*
 * the win screen, not something bolted on after it.
 *
 * The time is the headline now, but as a plain icon + line rather than the
 * old boxed "Linkage #N — solved in M:SS" bar -- the four stat tiles and the
 * distribution chart below it (today's solve highlighted in its bucket) are
 * what actually changed this game. Share content is still exactly
 * `buildShareText()` — puzzle number, time, hints used — this card just no
 * longer mirrors that whole line on screen.
 */

import { useState } from 'react';
import { bucketFor, formatTime } from '../engine/stats';
import type { ShareParts } from '../engine/shareText';
import type { Stats } from '../engine/types';
import { DistributionChart } from './DistributionChart';
import { TimerIcon } from './icons';
import { Modal } from './Modal';
import { StatCard } from './StatsModal';

export interface ShareModalProps {
  open: boolean;
  onClose: () => void;
  /** The single pasteable line -- what actually lands on the clipboard. */
  shareText: string;
  /** Only `hintNote` is shown on screen; the headline is clipboard-only now. */
  shareParts: ShareParts;
  /** e.g. "🎉 Perfect!" — tiered by attempts taken (SubmitBar owns the tiers). */
  celebration: string;
  /** Frozen solve time -- both the caption line and which histogram bucket lights up. */
  finalElapsedMs: number;
  /** Post-win stats, already folded in by the caller (recordResult already ran). */
  stats: Stats;
}

export function ShareModal({
  open,
  onClose,
  shareText,
  shareParts,
  celebration,
  finalElapsedMs,
  stats,
}: ShareModalProps) {
  const [copied, setCopied] = useState(false);
  const average =
    stats.gamesPlayed === 0 ? null : Math.round(stats.totalTimeMs / stats.gamesPlayed);

  const close = () => {
    setCopied(false);
    onClose();
  };

  return (
    <Modal open={open} onClose={close}>
      <div className="flex w-[340px] flex-col items-center gap-4 p-6">
        <span className="text-[22px] font-semibold tracking-[0.01em]">{celebration}</span>

        <div className="flex flex-col items-center gap-1">
          <div className="flex items-center gap-1.5">
            <span className="font-data text-[19px] font-semibold tracking-[-0.02em] text-ink">
              Solved in
            </span>
            <span className="text-accent">
              <TimerIcon size={18} />
            </span>
            <span className="font-data text-[19px] font-semibold tracking-[-0.02em] text-ink">
              {formatTime(finalElapsedMs)}
            </span>
          </div>
          {shareParts.hintNote !== null && (
            <span className="text-[13px] font-medium text-ink-muted">{shareParts.hintNote}</span>
          )}
        </div>

        <div className="grid w-full grid-cols-2 gap-2.5">
          <StatCard value={String(stats.currentStreak)} label="Current streak" accent compact />
          <StatCard value={String(stats.gamesPlayed)} label="Played" compact />
          <StatCard
            value={stats.bestTimeMs === null ? '—' : formatTime(stats.bestTimeMs)}
            label="Best time"
            compact
          />
          <StatCard
            value={average === null ? '—' : formatTime(average)}
            label="Average time"
            compact
          />
        </div>

        <div className="w-full">
          <DistributionChart
            distribution={stats.distribution}
            highlightIndex={bucketFor(finalElapsedMs)}
          />
        </div>

        <div className="flex w-full gap-2.5">
          <button
            type="button"
            className="ring-focus min-h-12 flex-1 rounded-lg bg-ground text-[15px] font-semibold text-ink"
            onClick={close}
          >
            Cancel
          </button>
          <button
            type="button"
            className="ring-focus min-h-12 flex-1 rounded-lg bg-accent text-[15px] font-semibold text-ground"
            onClick={() => {
              navigator.clipboard
                .writeText(shareText)
                .then(() => {
                  setCopied(true);
                  setTimeout(() => setCopied(false), 1_500);
                })
                // Clipboard access can be denied; the game itself already succeeded.
                .catch(() => undefined);
            }}
          >
            {copied ? 'Copied!' : 'Share'}
          </button>
        </div>
      </div>
    </Modal>
  );
}
