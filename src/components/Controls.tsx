import { useRef, type PointerEvent } from 'react'
import type { ButtonName, Direction, StickName, TriggerName } from '../types/controller'

export function GameButton({ name, label, pressed, onChange }: { name: ButtonName | Direction; label: string; pressed: boolean; onChange: (name: string, down: boolean) => void }) {
  return <button className={`game-button ${pressed ? 'pressed' : ''}`} aria-label={label} aria-pressed={pressed} onPointerDown={(event) => { event.preventDefault(); event.currentTarget.setPointerCapture(event.pointerId); onChange(name, true) }} onPointerUp={() => onChange(name, false)} onPointerCancel={() => onChange(name, false)} onLostPointerCapture={() => onChange(name, false)}>{label}</button>
}

export function FaceButtons({ pressed, onChange }: { pressed: Set<string>; onChange: (name: string, down: boolean) => void }) {
  return <div className="face-buttons">{(['Y', 'X', 'B', 'A'] as ButtonName[]).map((name) => <GameButton key={name} name={name} label={name} pressed={pressed.has(name)} onChange={onChange} />)}</div>
}

export function Dpad({ pressed, onChange }: { pressed: Set<string>; onChange: (name: string, down: boolean) => void }) {
  const ref = useRef<HTMLDivElement>(null); const pointer = useRef<number | null>(null)
  const update = (event: PointerEvent) => {
    if (pointer.current !== event.pointerId || !ref.current) return
    const rect = ref.current.getBoundingClientRect(); const dx = event.clientX - (rect.left + rect.width / 2); const dy = event.clientY - (rect.top + rect.height / 2)
    const distance = Math.hypot(dx, dy); const directions: Direction[][] = [['RIGHT'], ['RIGHT', 'DOWN'], ['DOWN'], ['DOWN', 'LEFT'], ['LEFT'], ['LEFT', 'UP'], ['UP'], ['UP', 'RIGHT']]
    const active = distance < rect.width * .14 ? [] : directions[Math.round((Math.atan2(dy, dx) * 180 / Math.PI + 360) % 360 / 45) % 8]
    ;(['UP', 'DOWN', 'LEFT', 'RIGHT'] as Direction[]).forEach((name) => onChange(name, active.includes(name)))
  }
  const release = () => { pointer.current = null; (['UP', 'DOWN', 'LEFT', 'RIGHT'] as Direction[]).forEach((name) => onChange(name, false)) }
  return <div ref={ref} className="dpad" aria-label="Directional pad" onPointerDown={(event) => { event.preventDefault(); pointer.current = event.pointerId; ref.current?.setPointerCapture(event.pointerId); update(event) }} onPointerMove={update} onPointerUp={release} onPointerCancel={release} onLostPointerCapture={release}>{(['UP', 'DOWN', 'LEFT', 'RIGHT'] as Direction[]).map((name) => <span key={name} className={`dpad-arm ${name.toLowerCase()} ${pressed.has(name) ? 'pressed' : ''}`} aria-hidden="true">{name === 'UP' ? '▲' : name === 'DOWN' ? '▼' : name === 'LEFT' ? '◀' : '▶'}</span>)}<span className="dpad-hub" /></div>
}

export function Trigger({ name, value, onValue }: { name: TriggerName; value: number; onValue: (value: number) => void }) {
  const ref = useRef<HTMLDivElement>(null); const pointer = useRef<number | null>(null); const startY = useRef(0)
  const move = (event: PointerEvent) => { if (pointer.current === event.pointerId) onValue(Math.max(0, Math.min(1, 1 - (startY.current - event.clientY) / 72))) }
  const release = () => { pointer.current = null; onValue(0) }
  return <div ref={ref} className={`trigger ${value > 0 ? 'pressed' : ''}`} role="slider" aria-label={`${name} analog trigger`} aria-valuemin={0} aria-valuemax={1} aria-valuenow={value} onPointerDown={(event) => { event.preventDefault(); pointer.current = event.pointerId; startY.current = event.clientY; ref.current?.setPointerCapture(event.pointerId); onValue(1) }} onPointerMove={move} onPointerUp={release} onPointerCancel={release} onLostPointerCapture={release}><span style={{ height: `${value * 100}%` }} /><b>{name}</b></div>
}

export function Stick({ name, label, onMove }: { name: StickName; label: string; onMove: (x: number, y: number) => void }) {
  const zone = useRef<HTMLDivElement>(null); const base = useRef<HTMLDivElement>(null); const knob = useRef<HTMLDivElement>(null); const pointer = useRef<number | null>(null)
  const origin = useRef({ x: 0, y: 0 }); const radius = useRef(1)
  const move = (event: PointerEvent) => {
    if (pointer.current !== event.pointerId || !zone.current || !base.current || !knob.current) return
    let dx = event.clientX - origin.current.x; let dy = event.clientY - origin.current.y; const distance = Math.hypot(dx, dy)
    if (distance > radius.current) { dx *= radius.current / distance; dy *= radius.current / distance }
    knob.current.style.transform = `translate(${dx}px, ${dy}px)`; onMove(dx / radius.current, dy / radius.current)
  }
  const release = () => { pointer.current = null; if (base.current && knob.current) { base.current.style.left = '50%'; base.current.style.top = '50%'; knob.current.style.transform = 'translate(0, 0)' }; onMove(0, 0) }
  return <div ref={zone} className="stick-zone" aria-label={`${name} analog stick`} onPointerDown={(event) => { event.preventDefault(); pointer.current = event.pointerId; zone.current?.setPointerCapture(event.pointerId); const rect = zone.current!.getBoundingClientRect(); const size = base.current!.offsetWidth; radius.current = size * .38; const x = Math.min(Math.max(event.clientX - rect.left, size / 2), rect.width - size / 2); const y = Math.min(Math.max(event.clientY - rect.top, size / 2), rect.height - size / 2); base.current!.style.left = `${x}px`; base.current!.style.top = `${y}px`; origin.current = { x: rect.left + x, y: rect.top + y }; move(event) }} onPointerMove={move} onPointerUp={release} onPointerCancel={release} onLostPointerCapture={release}><div ref={base} className="stick-base"><div ref={knob} className="stick-knob"><span>{label}</span></div></div></div>
}
