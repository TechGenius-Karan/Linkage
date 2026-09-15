/**
 * Presentation tier. Rules, reachable any time (planning.md 8.5.1).
 */

import { CheckIcon, HintIcon, TimerIcon } from './icons';
import { Modal } from './Modal';

export interface HowToPlayModalProps {
  open: boolean;
  onClose: () => void;
}

/** The four rungs between START and END, fading out — same shape as the real
 * board (Board.tsx), miniaturised into an icon rather than redrawn as one. */
function ChainDiagram() {
  return (
    <div className="-mt-1.5 flex w-[62px] flex-none flex-col gap-[3px]">
      <div className="flex h-[11px] items-center rounded bg-rule pl-1">
        <span className="text-[6.5px] font-bold tracking-[0.08em] text-ink-muted">START</span>
      </div>
      {[1, 0.72, 0.48, 0.3].map((opacity, i) => (
        <div key={i} className="h-[11px] rounded bg-accent" style={{ opacity }} />
      ))}
      <div className="flex h-[11px] items-center rounded bg-rule pl-1">
        <span className="text-[6.5px] font-bold tracking-[0.08em] text-ink-muted">END</span>
      </div>
    </div>
  );
}

function RuleRow({
  icon,
  title,
  children,
  last = false,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
  last?: boolean;
}) {
  return (
    <div
      className={`flex items-center gap-3.5 pt-[17px] ${last ? 'pb-[19px]' : 'border-b border-rule pb-[17px]'}`}
    >
      {icon}
      <div className="flex flex-col gap-[3px]">
        <span className="text-[15.5px] font-bold tracking-[-0.005em]">{title}</span>
        <span className="text-[13.5px] leading-[1.5] text-ink-muted">{children}</span>
      </div>
    </div>
  );
}

export function HowToPlayModal({ open, onClose }: HowToPlayModalProps) {
  return (
    <Modal open={open} onClose={onClose}>
      <div className="w-[340px] px-6 pb-[22px] pt-[26px]">
        <div className="flex items-start justify-between gap-3">
          <div className="flex flex-col gap-[5px]">
            <span className="font-word text-[27px] font-semibold leading-[1.05] tracking-[-0.015em]">
              How to play
            </span>
            <span className="text-[12px] font-semibold tracking-[0.14em] text-accent">
              LINKAGE &middot; 4 RULES
            </span>
          </div>
          <button
            type="button"
            className="ring-focus grid h-8 w-8 flex-none place-items-center rounded-full bg-ground text-ink-muted transition-colors hover:bg-accent-sub hover:text-ink"
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

        <div className="mt-5 mb-1 h-px bg-rule" />

        <div className="flex flex-col">
          <RuleRow icon={<ChainDiagram />} title="Build the chain">
            Fill the four rungs with words from the bank so each one links to the next, START to
            END.
          </RuleRow>

          <RuleRow
            icon={
              <div className="-mt-1.5 flex w-[62px] flex-none justify-center">
                <span className="grid h-7 w-7 place-items-center rounded-full bg-accent text-ground">
                  <CheckIcon />
                </span>
              </div>
            }
            title="Check your guess"
          >
            Check shows how many of the four are correct, not which ones.
          </RuleRow>

          <RuleRow
            icon={
              <div className="-mt-1.5 flex w-[62px] flex-none flex-col items-center gap-[3px] text-moon">
                <HintIcon size={34} />
                <span className="font-data text-[15px] font-medium">+20s</span>
              </div>
            }
            title="Hints cost time"
          >
            A hint reveals one word that belongs, but not where. Two per puzzle, 20 seconds each.
          </RuleRow>

          <RuleRow
            icon={
              <div className="-mt-1.5 flex w-[62px] flex-none justify-center text-accent">
                <TimerIcon />
              </div>
            }
            title="Guess freely"
            last
          >
            No limit on guesses. Only the clock is against you.
          </RuleRow>
        </div>

        <button
          type="button"
          className="ring-focus mt-1 h-[50px] w-full rounded-[15px] bg-accent text-[15.5px] font-bold tracking-[0.005em] text-ground transition-[filter,transform] hover:brightness-[1.07] active:scale-[0.99]"
          onClick={onClose}
        >
          Got it
        </button>
      </div>
    </Modal>
  );
}
