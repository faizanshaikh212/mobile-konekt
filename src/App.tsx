import { useCallback, useEffect, useRef, useState } from 'react'
import './App.css'

type Connection = 'connecting' | 'connected' | 'reconnecting' | 'error'
type ButtonName =
  | 'A' | 'B' | 'X' | 'Y' | 'LB' | 'RB' | 'LS' | 'RS' | 'SELECT' | 'START'
type Direction = 'UP' | 'DOWN' | 'LEFT' | 'RIGHT'

function App() {
  const socket = useRef<WebSocket | null>(null)
  const connectRef = useRef<() => void>(() => {})
  const reconnectTimer = useRef<number | undefined>(undefined)
  const held = useRef(new Set<string>())
  const [connection, setConnection] = useState<Connection>('connecting')
  const [player, setPlayer] = useState<number | null>(null)
  const [error, setError] = useState('')
  const [haptics, setHaptics] = useState(true)
  const [fullscreen, setFullscreen] = useState(false)
  const [pressed, setPressed] = useState<Set<string>>(new Set())
  const [triggerValues, setTriggerValues] = useState({ LT: 0, RT: 0 })
  const wakeLock = useRef<WakeLockSentinel | null>(null)

  const vibrate = useCallback((duration = 8) => {
    if (haptics && navigator.vibrate) navigator.vibrate(duration)
  }, [haptics])

  const send = useCallback((message: Record<string, unknown>) => {
    if (socket.current?.readyState === WebSocket.OPEN) socket.current.send(JSON.stringify(message))
  }, [])

  const setButton = useCallback((name: string, down: boolean) => {
    const isHeld = held.current.has(name)
    if (isHeld === down) return
    if (down) held.current.add(name)
    else held.current.delete(name)
    setPressed(new Set(held.current))
    send({ type: 'button', button: name, pressed: down })
    if (down) vibrate()
  }, [send, vibrate])

  const connect = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${protocol}//${window.location.hostname}:8081`)
    socket.current = ws
    setConnection('connecting')
    ws.onopen = () => {
      setConnection('connected')
      setError('')
      reconnectTimer.current = undefined
      if ('wakeLock' in navigator) navigator.wakeLock?.request('screen').then((lock) => { wakeLock.current = lock }).catch(() => {})
    }
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as { player?: number; error?: string }
        if (data.player) setPlayer(data.player)
        if (data.error) { setError(data.error); setConnection('error') }
      } catch { /* Ignore malformed server messages. */ }
    }
    ws.onclose = () => {
      setConnection('reconnecting')
      setPlayer(null)
      if (!reconnectTimer.current) reconnectTimer.current = window.setTimeout(() => connectRef.current(), 900)
    }
    ws.onerror = () => ws.close()
  }, [])
  useEffect(() => {
    connectRef.current = connect
    const initialConnection = window.setTimeout(connect, 0)
    return () => {
      window.clearTimeout(initialConnection)
      if (reconnectTimer.current) window.clearTimeout(reconnectTimer.current)
      socket.current?.close()
      wakeLock.current?.release().catch(() => {})
    }
  }, [connect])

  useEffect(() => {
    const reset = () => {
      held.current.forEach((name) => send({ type: 'button', button: name, pressed: false }))
      held.current.clear()
      setPressed(new Set())
      send({ type: 'trigger', trigger: 'LT', value: 0 })
      send({ type: 'trigger', trigger: 'RT', value: 0 })
      send({ type: 'stick', stick: 'LEFT', x: 0, y: 0 })
      send({ type: 'stick', stick: 'RIGHT', x: 0, y: 0 })
      setTriggerValues({ LT: 0, RT: 0 })
    }
    window.addEventListener('blur', reset)
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible' && 'wakeLock' in navigator) navigator.wakeLock?.request('screen').then((lock) => { wakeLock.current = lock }).catch(() => {})
    })
    return () => window.removeEventListener('blur', reset)
  }, [send])

  const toggleFullscreen = async () => {
    if (document.fullscreenElement) await document.exitFullscreen()
    else await document.documentElement.requestFullscreen?.()
    setFullscreen(Boolean(document.fullscreenElement))
  }

  return (
    <main className="controller" aria-label="MobileKonekt gamepad">
      <header className="topbar">
        <div className="brand"><span className="brand-mark" aria-hidden="true">✦</span><span>Mobile<span className="brand-accent">Konekt</span></span></div>
        <div className={`connection ${connection}`} role="status"><span className="status-dot" />{error || (connection === 'connected' ? `Player ${player ?? '—'} connected` : connection === 'reconnecting' ? 'Reconnecting…' : 'Connecting…')}</div>
        <div className="toolbar">
          <button className={`tool-button ${haptics ? 'active' : ''}`} aria-pressed={haptics} onClick={() => setHaptics((value) => !value)}><span aria-hidden="true">⌁</span><span className="tool-label">Haptics</span></button>
          <button className="tool-button" aria-pressed={fullscreen} onClick={() => void toggleFullscreen()}><span aria-hidden="true">{fullscreen ? '⤢' : '⛶'}</span><span className="tool-label">Fullscreen</span></button>
        </div>
      </header>

      <section className="deck">
        <div className="side left-side">
          <div className="shoulders"><Trigger name="LT" value={triggerValues.LT} onValue={(value) => { setTriggerValues((v) => ({ ...v, LT: value })); send({ type: 'trigger', trigger: 'LT', value }) }} /><GameButton name="LB" label="LB" pressed={pressed.has('LB')} onChange={setButton} /></div>
          <Dpad onChange={(name, down) => setButton(name, down)} pressed={pressed} />
          <div className="stick-row"><Stick name="LEFT" label="L" onMove={(x, y) => send({ type: 'stick', stick: 'LEFT', x, y })} /><GameButton name="LS" label="LS" pressed={pressed.has('LS')} onChange={setButton} /></div>
        </div>
        <div className="center-controls">
          <div className="center-logo">MK <span>GAMEPAD</span></div>
          <div className="system-buttons"><GameButton name="SELECT" label="SELECT" pressed={pressed.has('SELECT')} onChange={setButton} /><GameButton name="START" label="START" pressed={pressed.has('START')} onChange={setButton} /></div>
        </div>
        <div className="side right-side">
          <div className="shoulders"><GameButton name="RB" label="RB" pressed={pressed.has('RB')} onChange={setButton} /><Trigger name="RT" value={triggerValues.RT} onValue={(value) => { setTriggerValues((v) => ({ ...v, RT: value })); send({ type: 'trigger', trigger: 'RT', value }) }} /></div>
          <FaceButtons pressed={pressed} onChange={setButton} />
          <div className="stick-row"><GameButton name="RS" label="RS" pressed={pressed.has('RS')} onChange={setButton} /><Stick name="RIGHT" label="R" onMove={(x, y) => send({ type: 'stick', stick: 'RIGHT', x, y })} /></div>
        </div>
      </section>
      <div className="rotate-hint"><span aria-hidden="true">↻</span> Rotate your device for the best experience</div>
    </main>
  )
}

function GameButton({ name, label, pressed, onChange }: { name: ButtonName; label: string; pressed: boolean; onChange: (name: string, down: boolean) => void }) {
  return <button className={`game-button ${pressed ? 'pressed' : ''}`} aria-label={label} aria-pressed={pressed} onPointerDown={(event) => { event.preventDefault(); event.currentTarget.setPointerCapture(event.pointerId); onChange(name, true) }} onPointerUp={() => onChange(name, false)} onPointerCancel={() => onChange(name, false)} onLostPointerCapture={() => onChange(name, false)}>{label}</button>
}

function FaceButtons({ pressed, onChange }: { pressed: Set<string>; onChange: (name: string, down: boolean) => void }) {
  return <div className="face-buttons">{(['Y', 'X', 'B', 'A'] as ButtonName[]).map((name) => <GameButton key={name} name={name} label={name} pressed={pressed.has(name)} onChange={onChange} />)}</div>
}

function Dpad({ pressed, onChange }: { pressed: Set<string>; onChange: (name: string, down: boolean) => void }) {
  const ref = useRef<HTMLDivElement>(null)
  const pointer = useRef<number | null>(null)
  const update = (event: React.PointerEvent) => {
    if (pointer.current !== event.pointerId || !ref.current) return
    const rect = ref.current.getBoundingClientRect()
    const dx = event.clientX - (rect.left + rect.width / 2)
    const dy = event.clientY - (rect.top + rect.height / 2)
    const distance = Math.hypot(dx, dy)
    const active: Direction[] = distance < rect.width * .14 ? [] : [['RIGHT'], ['RIGHT', 'DOWN'], ['DOWN'], ['DOWN', 'LEFT'], ['LEFT'], ['LEFT', 'UP'], ['UP'], ['UP', 'RIGHT']][Math.round((Math.atan2(dy, dx) * 180 / Math.PI + 360) % 360 / 45) % 8] as Direction[]
    ;(['UP', 'DOWN', 'LEFT', 'RIGHT'] as Direction[]).forEach((name) => onChange(name, active.includes(name)))
  }
  const release = () => { pointer.current = null; (['UP', 'DOWN', 'LEFT', 'RIGHT'] as Direction[]).forEach((name) => onChange(name, false)) }
  return <div ref={ref} className="dpad" aria-label="Directional pad" onPointerDown={(event) => { event.preventDefault(); pointer.current = event.pointerId; ref.current?.setPointerCapture(event.pointerId); update(event) }} onPointerMove={update} onPointerUp={release} onPointerCancel={release} onLostPointerCapture={release}>{(['UP', 'DOWN', 'LEFT', 'RIGHT'] as Direction[]).map((name) => <span key={name} className={`dpad-arm ${name.toLowerCase()} ${pressed.has(name) ? 'pressed' : ''}`} aria-hidden="true">{name === 'UP' ? '▲' : name === 'DOWN' ? '▼' : name === 'LEFT' ? '◀' : '▶'}</span>)}<span className="dpad-hub" /></div>
}

function Trigger({ name, value, onValue }: { name: 'LT' | 'RT'; value: number; onValue: (value: number) => void }) {
  const ref = useRef<HTMLDivElement>(null)
  const pointer = useRef<number | null>(null)
  const startY = useRef(0)
  const move = (event: React.PointerEvent) => { if (pointer.current !== event.pointerId) return; onValue(Math.max(0, Math.min(1, 1 - (startY.current - event.clientY) / 72))) }
  const release = () => { pointer.current = null; onValue(0) }
  return <div ref={ref} className={`trigger ${value > 0 ? 'pressed' : ''}`} role="slider" aria-label={`${name} analog trigger`} aria-valuemin={0} aria-valuemax={1} aria-valuenow={value} onPointerDown={(event) => { event.preventDefault(); pointer.current = event.pointerId; startY.current = event.clientY; ref.current?.setPointerCapture(event.pointerId); onValue(1) }} onPointerMove={move} onPointerUp={release} onPointerCancel={release} onLostPointerCapture={release}><span style={{ height: `${value * 100}%` }} /><b>{name}</b></div>
}

function Stick({ name, label, onMove }: { name: 'LEFT' | 'RIGHT'; label: string; onMove: (x: number, y: number) => void }) {
  const zone = useRef<HTMLDivElement>(null)
  const base = useRef<HTMLDivElement>(null)
  const knob = useRef<HTMLDivElement>(null)
  const pointer = useRef<number | null>(null)
  const origin = useRef({ x: 0, y: 0 })
  const radius = useRef(1)
  const pending = useRef({ x: 0, y: 0 })
  const sent = useRef({ x: 0, y: 0 })
  const frame = useRef<number | null>(null)
  const flush = () => { frame.current = null; if (Math.abs(sent.current.x - pending.current.x) > .01 || Math.abs(sent.current.y - pending.current.y) > .01) { sent.current = pending.current; onMove(sent.current.x, sent.current.y) } }
  const move = (event: React.PointerEvent) => {
    if (pointer.current !== event.pointerId || !zone.current || !base.current || !knob.current) return
    let dx = event.clientX - origin.current.x; let dy = event.clientY - origin.current.y
    const distance = Math.hypot(dx, dy); if (distance > radius.current) { dx *= radius.current / distance; dy *= radius.current / distance }
    knob.current.style.transform = `translate(${dx}px, ${dy}px)`; pending.current = { x: dx / radius.current, y: dy / radius.current }
    if (!frame.current) frame.current = requestAnimationFrame(flush)
  }
  const release = () => { pointer.current = null; if (base.current && knob.current) { base.current.style.left = '50%'; base.current.style.top = '50%'; knob.current.style.transform = 'translate(0, 0)' }; pending.current = { x: 0, y: 0 }; onMove(0, 0) }
  return <div ref={zone} className="stick-zone" aria-label={`${name} analog stick`} onPointerDown={(event) => { event.preventDefault(); pointer.current = event.pointerId; zone.current?.setPointerCapture(event.pointerId); const rect = zone.current!.getBoundingClientRect(); const size = base.current!.offsetWidth; radius.current = size * .38; const x = Math.min(Math.max(event.clientX - rect.left, size / 2), rect.width - size / 2); const y = Math.min(Math.max(event.clientY - rect.top, size / 2), rect.height - size / 2); base.current!.style.left = `${x}px`; base.current!.style.top = `${y}px`; origin.current = { x: rect.left + x, y: rect.top + y }; move(event) }} onPointerMove={move} onPointerUp={release} onPointerCancel={release} onLostPointerCapture={release}><div ref={base} className="stick-base"><div ref={knob} className="stick-knob"><span>{label}</span></div></div></div>
}

export default App
