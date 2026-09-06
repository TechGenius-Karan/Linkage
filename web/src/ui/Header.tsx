/**
 * Presentation tier. Wordmark, puzzle number, and the four affordances
 * (planning.md 8.5.1, docs/design.md 7).
 *
 * Props in, events out. Every handler is optional so Phase 3 can render the
 * header before any of the panels behind it exist — a missing handler renders
 * a disabled button rather than a button that lies about being live.
 */

import { HelpIcon, HintIcon, SettingsIcon, StatsIcon } from './icons';

export interface HeaderProps {
  puzzleNumber: number;
  onHint?: (() => void) | undefined;
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
      className="icon-btn ring-focus disabled:opacity-40"
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
  onHint,
  onStats,
  onHowToPlay,
  onSettings,
}: HeaderProps) {
  return (
    <header className="flex items-center justify-between gap-3">
      <div className="flex items-baseline gap-2">
        <span className="font-word text-[19px] font-semibold tracking-[0.01em]">Linkage</span>
        <span className="text-[13px] font-medium text-ink-muted">#{puzzleNumber}</span>
      </div>

      <div className="flex items-center gap-1">
        <Action label="Hint" onClick={onHint}>
          <HintIcon />
        </Action>
        <Action label="Statistics" onClick={onStats}>
          <StatsIcon />
        </Action>
        <Action label="How to play" onClick={onHowToPlay}>
          <HelpIcon />
        </Action>
        <Action label="Settings" onClick={onSettings}>
          <SettingsIcon />
        </Action>
      </div>
    </header>
  );
}
