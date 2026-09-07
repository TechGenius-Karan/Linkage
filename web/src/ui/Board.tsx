/**
 * Presentation tier. The ladder, and the slide gesture (planning.md 2.2, 2.4).
 *
 * `<Board>` owns the drag because a `<Slot>` cannot know which slot it was
 * dragged onto — only their common parent can. The slots stay pure functions
 * of props.
 *
 * **No drag library.** This is four items in a fixed-height vertical column,
 * which is the easiest possible case: track the pointer's Y delta, divide by
 * row pitch, clamp. `@dnd-kit` exists to solve sortable lists across arbitrary
 * containers with collision detection; we have one container of four rows, and
 * the bank -> slot direction is tap-only. Pointer events are already unified
 * across mouse, touch and pen, which is the reason HTML5 drag-and-drop was
 * rejected in the first place — it does not fire on touch.
 *
 * The reducer never learns dragging exists. This dispatches `MOVE_TILE`.
 */

import { useCallback, useRef, useState } from 'react';
import type { PointerEvent as ReactPointerEvent } from 'react';
import { AnchorWord } from './AnchorWord';
import { Slot, type SlotState } from './Slot';

export interface BoardProps {
  start: string;
  end: string;
  slots: (string | null)[];
  revealed?: string[] | undefined;
  onSlotClick?: ((index: number) => void) | undefined;
  onSlotRemove?: ((index: number) => void) | undefined;
  onMove?: ((from: number, to: number) => void) | undefined;
  onEscape?: (() => void) | undefined;
}

interface Drag {
  from: number;
  startY: number;
  offset: number;
  pitch: number;
}

/** Below this, a press is a tap and must not be read as a one-row slide. */
const DRAG_THRESHOLD_PX = 6;

export function Board({
  start,
  end,
  slots,
  revealed,
  onSlotClick,
  onSlotRemove,
  onMove,
  onEscape,
}: BoardProps) {
  const columnRef = useRef<HTMLDivElement>(null);
  const [drag, setDrag] = useState<Drag | null>(null);

  /** Row pitch measured from the DOM, so CSS stays the source of truth. */
  const measurePitch = useCallback((): number => {
    const nodes = columnRef.current?.querySelectorAll('[data-slot]');
    if (nodes === undefined || nodes.length < 2) return 0;
    const a = nodes[0]!.getBoundingClientRect();
    const b = nodes[1]!.getBoundingClientRect();
    return b.top - a.top;
  }, []);

  const targetOf = (d: Drag): number => {
    if (d.pitch === 0) return d.from;
    const moved = Math.round(d.offset / d.pitch);
    return Math.min(slots.length - 1, Math.max(0, d.from + moved));
  };

  const handleDragStart = (from: number, event: ReactPointerEvent<HTMLButtonElement>) => {
    if (onMove === undefined || event.button !== 0) return;
    // Capture so the gesture survives the pointer leaving the element — a
    // drag that dies mid-flight strands the row somewhere it was never
    // dropped.
    event.currentTarget.setPointerCapture(event.pointerId);
    setDrag({ from, startY: event.clientY, offset: 0, pitch: measurePitch() });
  };

  const handlePointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (drag === null) return;
    setDrag({ ...drag, offset: event.clientY - drag.startY });
  };

  const endDrag = () => {
    if (drag === null) return;
    const to = targetOf(drag);
    // Under the threshold this was a tap. Slot's own onClick has already
    // fired for it; moving here as well would double-handle the press.
    if (Math.abs(drag.offset) >= DRAG_THRESHOLD_PX && to !== drag.from) {
      onMove?.(drag.from, to);
    }
    setDrag(null);
  };

  const dropTarget = drag === null ? null : targetOf(drag);

  return (
    <div
      ref={columnRef}
      className="relative flex touch-none flex-col items-center gap-2.5"
      onPointerMove={handlePointerMove}
      onPointerUp={endDrag}
      // A cancelled pointer (a system gesture, a call arriving) must settle
      // the row rather than leave it floating.
      onPointerCancel={endDrag}
    >
      <div
        className="pointer-events-none absolute left-1/2 top-9 bottom-9 z-0 -ml-px w-0.5 bg-rule"
        aria-hidden="true"
      />

      <AnchorWord word={start} position="start" />

      {slots.map((word, i) => {
        // On a loss the chain replaces whatever the player had, rather than
        // filling their gaps. Their board is full of wrong tiles at that point,
        // so revealing only the empty slots revealed nothing -- and the message
        // beside it says "here is the chain".
        const reveal = revealed?.[i];
        const state: SlotState =
          reveal !== undefined ? 'reveal' : word !== null ? 'filled' : 'empty';
        return (
          <Slot
            key={i}
            index={i}
            word={reveal ?? word}
            state={state}
            dragOffset={drag?.from === i ? drag.offset : undefined}
            isDropTarget={dropTarget === i && drag?.from !== i}
            onClick={onSlotClick}
            onRemove={onSlotRemove}
            onNudge={
              onMove === undefined
                ? undefined
                : (index, direction) => {
                    const to = index + direction;
                    if (to >= 0 && to < slots.length) onMove(index, to);
                  }
            }
            onDragStart={handleDragStart}
            onEscape={onEscape}
          />
        );
      })}

      <AnchorWord word={end} position="end" />
    </div>
  );
}
