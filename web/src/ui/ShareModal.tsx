/**
 * Presentation tier. The win panel: celebration, time, and the share card
 * (planning.md 2.7). Opens by itself the moment a game is won — it *is* the
 * win screen, not something bolted on after it.
 *
 * Share content is exactly `buildShareText()` — puzzle number, time, hints
 * used. No emoji grid, no ladder recap: a nicer-looking presentation of the
 * same one-line, pasteable text the game has always produced.
 */

import { useState } from 'react';
import type { ShareParts } from '../engine/shareText';
import { Modal } from './Modal';

export interface ShareModalProps {
  open: boolean;
  onClose: () => void;
  /** The single pasteable line -- what actually lands on the clipboard. */
  shareText: string;
  /** Same content, split so the hint note can get its own centered row. */
  shareParts: ShareParts;
  /** e.g. "🎉 Perfect!" — tiered by attempts taken (SubmitBar owns the tiers). */
  celebration: string;
}

export function ShareModal({ open, onClose, shareText, shareParts, celebration }: ShareModalProps) {
  const [copied, setCopied] = useState(false);

  return (
    <Modal
      open={open}
      onClose={() => {
        setCopied(false);
        onClose();
      }}
    >
      <div className="relative flex w-[300px] flex-col items-center gap-5 p-6">
        <button
          type="button"
          className="icon-btn ring-focus absolute right-2 top-2"
          aria-label="Close"
          onClick={() => {
            setCopied(false);
            onClose();
          }}
        >
          <svg
            width="18"
            height="18"
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

        <span className="text-[22px] font-semibold tracking-[0.01em]">{celebration}</span>

        <div className="flex w-full flex-col items-center gap-1 rounded-lg border border-rule bg-ground px-4 py-3">
          <p className="text-center text-[15px] font-medium text-ink">{shareParts.headline}</p>
          {shareParts.hintNote !== null && (
            <p className="text-center text-[13px] font-medium text-ink-muted">
              {shareParts.hintNote}
            </p>
          )}
        </div>

        <button
          type="button"
          className="ring-focus min-h-12 rounded-lg bg-accent px-10 text-[15px] font-semibold text-ground"
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
    </Modal>
  );
}
