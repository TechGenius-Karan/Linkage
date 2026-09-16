/**
 * Presentation tier. Shared vocabulary for the one drag-and-drop context that
 * spans `<Board>` and `<WordBank>`.
 *
 * They're siblings, so neither can resolve a drop on its own — only their
 * common parent (`<Game>` in App.tsx) sees both a drag's origin and where it
 * landed. This file is what lets `<Game>` do that without either component
 * importing the other: a slot and a bank tile agree on an id scheme and a
 * shared `data` shape, and `<Game>` reads both off the `dnd-kit` drag event.
 */

export const BANK_DROPPABLE_ID = 'bank';

/** Below this, a press is a tap, not a drag (mirrors the old Board.tsx threshold). */
export const DRAG_ACTIVATION_DISTANCE_PX = 6;

export const slotDroppableId = (index: number): string => `slot:${index}`;

export const parseSlotDroppableId = (id: string): number | null => {
  const match = /^slot:(\d+)$/.exec(id);
  return match ? Number(match[1]) : null;
};

export const bankDraggableId = (word: string): string => `bank:${word}`;

export type DragOrigin = { origin: 'bank'; word: string } | { origin: 'slot'; index: number };
