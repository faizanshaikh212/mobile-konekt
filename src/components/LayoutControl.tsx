import { useRef, type PointerEvent, type ReactNode } from 'react'
import type { ControlId, Point } from '../types/controller'

type Props = { id: ControlId; point: Point; editing: boolean; onMove: (id: ControlId, point: Point) => void; className?: string; children: ReactNode }

export function LayoutControl({ id, point, editing, onMove, className = '', children }: Props) {
  const ref = useRef<HTMLDivElement>(null)
  const pointer = useRef<number | null>(null)
  const offset = useRef({ x: 0, y: 0 })
  const move = (event: PointerEvent) => {
    if (!editing || pointer.current !== event.pointerId || !ref.current?.parentElement) return
    const rect = ref.current.parentElement.getBoundingClientRect()
    onMove(id, {
      x: Math.max(4, Math.min(96, ((event.clientX - rect.left - offset.current.x) / rect.width) * 100)),
      y: Math.max(5, Math.min(95, ((event.clientY - rect.top - offset.current.y) / rect.height) * 100)),
    })
  }
  const end = () => { pointer.current = null }
  return <div ref={ref} className={`layout-control ${className} ${editing ? 'layout-control-editing' : ''}`} style={{ left: `${point.x}%`, top: `${point.y}%` }} onPointerDown={(event) => {
    if (!editing) return
    event.preventDefault(); event.stopPropagation(); pointer.current = event.pointerId
    const rect = event.currentTarget.getBoundingClientRect()
    offset.current = { x: event.clientX - (rect.left + rect.width / 2), y: event.clientY - (rect.top + rect.height / 2) }
    event.currentTarget.setPointerCapture(event.pointerId)
  }} onPointerMove={move} onPointerUp={end} onPointerCancel={end} onLostPointerCapture={end}>
    {editing && <span className="drag-grip" aria-hidden="true">⠿</span>}{children}
  </div>
}
