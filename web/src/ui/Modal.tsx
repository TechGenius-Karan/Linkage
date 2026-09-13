/**
 * Presentation tier. A generic modal built on native `<dialog>`.
 *
 * `showModal()` traps focus, restores it to the invoking element on close,
 * and closes on Escape — all for free (planning.md 8.6), so there's no
 * hand-rolled focus trap to get wrong.
 */

import { useEffect, useRef, type ReactNode } from 'react';

export interface ModalProps {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
}

export function Modal({ open, onClose, children }: ModalProps) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (dialog === null) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      className="rounded-2xl bg-surface text-ink shadow-lg"
      onClose={onClose}
      onClick={(e) => {
        if (e.target === ref.current) onClose();
      }}
    >
      {children}
    </dialog>
  );
}
