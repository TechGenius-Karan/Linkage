/**
 * Presentation tier. Dark mode, the one agreed settings item (planning.md 8.5.1).
 */

import { useState } from 'react';
import { getThemePreference, setThemePreference } from '../data/theme';
import type { ThemePreference } from '../engine/types';
import { Modal } from './Modal';

export interface SettingsModalProps {
  open: boolean;
  onClose: () => void;
}

const OPTIONS: { value: ThemePreference; label: string }[] = [
  { value: 'light', label: 'Light' },
  { value: 'dark', label: 'Dark' },
  { value: 'system', label: 'System' },
];

export function SettingsModal({ open, onClose }: SettingsModalProps) {
  const [pref, setPref] = useState(getThemePreference);

  return (
    <Modal open={open} onClose={onClose}>
      <div className="flex w-[300px] flex-col gap-5 p-6">
        <span className="font-word text-[19px] font-semibold tracking-[0.01em]">Settings</span>

        <div>
          <p className="mb-2 text-[13px] font-medium text-ink-muted">Appearance</p>
          <div className="flex rounded-lg border border-rule p-1">
            {OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                className={`ring-focus flex-1 rounded-md py-2 text-[13px] font-medium ${
                  pref === opt.value ? 'bg-accent text-ground' : 'text-ink-muted'
                }`}
                onClick={() => {
                  setThemePreference(opt.value);
                  setPref(opt.value);
                }}
              >
                {opt.label}
              </button>
            ))}
          </div>
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
