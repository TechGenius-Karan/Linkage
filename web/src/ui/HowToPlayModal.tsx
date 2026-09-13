/**
 * Presentation tier. Rules, reachable any time (planning.md 8.5.1).
 */

import { Modal } from './Modal';

export interface HowToPlayModalProps {
  open: boolean;
  onClose: () => void;
}

export function HowToPlayModal({ open, onClose }: HowToPlayModalProps) {
  return (
    <Modal open={open} onClose={onClose}>
      <div className="flex w-[300px] flex-col gap-4 p-6">
        <span className="font-word text-[19px] font-semibold tracking-[0.01em]">How to play</span>

        <ul className="flex flex-col gap-3 text-[15px] text-ink">
          <li>Fill the four rungs with words from the bank so the chain connects START to END.</li>
          <li>Check shows how many of the four are correct — not which ones.</li>
          <li>A hint reveals one word in the chain, but costs 20 seconds.</li>
          <li>No limit on guesses. Only the clock is against you.</li>
        </ul>

        <button
          type="button"
          className="ring-focus min-h-12 rounded-lg bg-accent text-[15px] font-semibold text-ground"
          onClick={onClose}
        >
          Got it
        </button>
      </div>
    </Modal>
  );
}
