/**
 * Presentation tier. Wordmark, puzzle number, and the four affordances
 * (planning.md 8.5.1, docs/design.md 7).
 *
 * Props in, events out. Every handler is optional so Phase 3 can render the
 * header before any of the panels behind it exist — a missing handler renders
 * a disabled button rather than a button that lies about being live.
 */

import { HelpIcon, SettingsIcon, StatsIcon } from './icons';

export interface HeaderProps {
  puzzleNumber: number | null;
  onStats?: (() => void) | undefined;
  onHowToPlay?: (() => void) | undefined;
  onSettings?: (() => void) | undefined;
}

interface ActionProps {
  label: string;
  onClick: (() => void) | undefined;
  children: React.ReactNode;
}

function Action({ label, onClick, children }: ActionProps) {
  return (
    <button
      type="button"
      className="icon-btn ring-focus"
      aria-label={label}
      title={label}
      onClick={onClick}
      disabled={onClick === undefined}
    >
      {children}
    </button>
  );
}

export function Header({
  puzzleNumber,
  onStats,
  onHowToPlay,
  onSettings,
}: HeaderProps) {
  return (
    <header className="flex items-center justify-between gap-3">
      <div className="flex items-baseline gap-2">
        <span className="font-word text-[19px] font-semibold tracking-[0.01em]">Linkage</span>
        {/* null until a puzzle has actually loaded -- before then (or on a
            day the archive skipped) there is no number to guess at. */}
        {puzzleNumber !== null && (
          <span className="text-[17px] font-medium text-ink-muted">#{puzzleNumber}</span>
        )}
      </div>

      <div className="flex items-center gap-4">
        <Action label="Statistics" onClick={onStats}>
          <StatsIcon size={26} />
        </Action>
        <Action label="How to play" onClick={onHowToPlay}>
          <HelpIcon size={26} />
        </Action>
        <Action label="Settings" onClick={onSettings}>
          <SettingsIcon size={26} />
        </Action>
      </div>
    </header>
  );
}
