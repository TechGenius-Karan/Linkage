/**
 * Presentation tier. The solve-time histogram bars, shared by `StatsModal`
 * (all-time view) and `ShareModal` (today's solve highlighted in its bucket).
 */

import { BUCKET_LABELS } from '../engine/stats';

export interface DistributionChartProps {
  distribution: number[];
  /** Bucket index to accent-highlight, or `null` for no highlight. */
  highlightIndex: number | null;
}

export function DistributionChart({ distribution, highlightIndex }: DistributionChartProps) {
  const max = Math.max(1, ...distribution);

  return (
    <div className="flex flex-col gap-[7px]">
      {distribution.map((count, i) => {
        const highlighted = count > 0 && i === highlightIndex;
        const barColor = count === 0 ? 'bg-rule' : highlighted ? 'bg-accent' : 'bg-accent-sub';
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
              className={`w-4 flex-none text-right font-data text-[11.5px] font-semibold ${highlighted ? 'text-accent' : 'text-ink-muted'}`}
            >
              {count}
            </span>
          </div>
        );
      })}
    </div>
  );
}
