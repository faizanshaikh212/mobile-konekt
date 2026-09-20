import { useRef, type PointerEvent, type ReactNode } from "react";
import type { ControlId, GridMode, Point } from "../types/controller";

type Props = {
  id: ControlId;
  point: Point;
  editing: boolean;
  onMove: (id: ControlId, point: Point) => void;
  onResize: (id: ControlId, scale: number) => void;
  grid?: GridMode;
  gridStep?: { x: number; y: number };
  className?: string;
  children: ReactNode;
};

export function LayoutControl({
  id,
  point,
  editing,
  onMove,
  onResize,
  grid = "none",
  gridStep = { x: 0, y: 0 },
  className = "",
  children,
}: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const pointer = useRef<number | null>(null);
  const resizePointer = useRef<number | null>(null);
  const resizeStart = useRef({ x: 0, y: 0, distance: 1, scale: 1 });
  const offset = useRef({ x: 0, y: 0 });
  const move = (event: PointerEvent) => {
    if (
      !editing ||
      pointer.current !== event.pointerId ||
      !ref.current?.parentElement
    )
      return;
    const rect = ref.current.parentElement.getBoundingClientRect();
    const raw = {
      x: Math.max(
        4,
        Math.min(
          96,
          ((event.clientX - rect.left - offset.current.x) / rect.width) * 100,
        ),
      ),
      y: Math.max(
        5,
        Math.min(
          95,
          ((event.clientY - rect.top - offset.current.y) / rect.height) * 100,
        ),
      ),
    };
    const snapX = grid === "none" ? 0 : gridStep.x;
    const snapY = grid === "none" ? 0 : gridStep.y;
    onMove(
      id,
      snapX > 0 && snapY > 0
        ? {
            x: Math.max(4, Math.min(96, Math.round(raw.x / snapX) * snapX)),
            y: Math.max(5, Math.min(95, Math.round(raw.y / snapY) * snapY)),
          }
        : raw,
    );
  };
  const end = () => {
    pointer.current = null;
  };
  const resize = (event: PointerEvent) => {
    if (
      resizePointer.current !== event.pointerId ||
      !ref.current?.parentElement
    )
      return;
    const distance = Math.hypot(
      event.clientX - resizeStart.current.x,
      event.clientY - resizeStart.current.y,
    );
    const next = Math.max(
      0.5,
      Math.min(2, resizeStart.current.scale * distance / resizeStart.current.distance),
    );
    onResize(id, Number(next.toFixed(2)));
  };
  const endResize = () => {
    resizePointer.current = null;
  };
  return (
    <div
      ref={ref}
      className={`layout-control ${className} ${editing ? "layout-control-editing" : ""}`}
      style={{
        left: `${point.x}%`,
        top: `${point.y}%`,
        transform: `translate(-50%, -50%) scale(${point.scale ?? 1})`,
      }}
      onPointerDown={(event) => {
        if (!editing) return;
        event.preventDefault();
        event.stopPropagation();
        pointer.current = event.pointerId;
        const rect = event.currentTarget.getBoundingClientRect();
        offset.current = {
          x: event.clientX - (rect.left + rect.width / 2),
          y: event.clientY - (rect.top + rect.height / 2),
        };
        event.currentTarget.setPointerCapture(event.pointerId);
      }}
      onPointerMove={move}
      onPointerUp={end}
      onPointerCancel={end}
      onLostPointerCapture={end}
    >
      {editing && (
        <span className="drag-grip" aria-hidden="true">
          ⠿
        </span>
      )}
      {editing && (
        <span
          className="resize-grip"
          aria-label={`Resize ${id}`}
          onPointerDown={(event) => {
            event.preventDefault();
            event.stopPropagation();
            resizePointer.current = event.pointerId;
            const rect = ref.current?.getBoundingClientRect();
            if (!rect) return;
            resizeStart.current = {
              x: rect.left + rect.width / 2,
              y: rect.top + rect.height / 2,
              distance: Math.max(
                1,
                Math.hypot(
                  event.clientX - (rect.left + rect.width / 2),
                  event.clientY - (rect.top + rect.height / 2),
                ),
              ),
              scale: point.scale ?? 1,
            };
            event.currentTarget.setPointerCapture(event.pointerId);
          }}
          onPointerMove={resize}
          onPointerUp={endResize}
          onPointerCancel={endResize}
          onLostPointerCapture={endResize}
        />
      )}
      {children}
    </div>
  );
}
