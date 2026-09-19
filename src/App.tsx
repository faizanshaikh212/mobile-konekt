import { useCallback, useEffect, useRef, useState } from 'react'
import './App.css'
import { Dpad, GameButton, Stick, Trigger } from './components/Controls'
import { LayoutControl } from './components/LayoutControl'
import { useLayout } from './hooks/useLayout'
import { PRESETS } from './presets'
import type { Connection } from './types/controller'

function App() {
  const socket = useRef<WebSocket | null>(null); const connectRef = useRef<() => void>(() => { }); const reconnectTimer = useRef<number | undefined>(undefined)
  const held = useRef(new Set<string>()); const wakeLock = useRef<WakeLockSentinel | null>(null)
  const [connection, setConnection] = useState<Connection>('connecting'); const [player, setPlayer] = useState<number | null>(null); const [error, setError] = useState('')
  const [haptics, setHaptics] = useState(true); const [fullscreen, setFullscreen] = useState(false); const [pressed, setPressed] = useState<Set<string>>(new Set()); const [triggerValues, setTriggerValues] = useState({ LT: 0, RT: 0 })
  const { layout, editing, startEditing, save, reset, applyPreset, move } = useLayout()
  const vibrate = useCallback((duration = 8) => { if (haptics && navigator.vibrate) navigator.vibrate(duration) }, [haptics])
  const send = useCallback((message: Record<string, unknown>) => { if (socket.current?.readyState === WebSocket.OPEN) socket.current.send(JSON.stringify(message)) }, [])
  const setButton = useCallback((name: string, down: boolean) => {
    if (held.current.has(name) === down) return
    if (down) held.current.add(name); else held.current.delete(name)
    setPressed(new Set(held.current)); send({ type: 'button', button: name, pressed: down }); if (down) vibrate()
  }, [send, vibrate])
  const connect = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'; const ws = new WebSocket(`${protocol}//${window.location.hostname}:8081`); socket.current = ws; setConnection('connecting')
    ws.onopen = () => { setConnection('connected'); setError(''); reconnectTimer.current = undefined; if ('wakeLock' in navigator) navigator.wakeLock?.request('screen').then((lock) => { wakeLock.current = lock }).catch(() => { }) }
    ws.onmessage = (event) => { try { const data = JSON.parse(event.data) as { player?: number; error?: string }; if (data.player) setPlayer(data.player); if (data.error) { setError(data.error); setConnection('error') } } catch { /* Ignore malformed server messages. */ } }
    ws.onclose = () => { setConnection('reconnecting'); setPlayer(null); if (!reconnectTimer.current) reconnectTimer.current = window.setTimeout(() => connectRef.current(), 900) }
    ws.onerror = () => ws.close()
  }, [])
  useEffect(() => { connectRef.current = connect; const initial = window.setTimeout(connect, 0); return () => { window.clearTimeout(initial); if (reconnectTimer.current) window.clearTimeout(reconnectTimer.current); socket.current?.close(); wakeLock.current?.release().catch(() => { }) } }, [connect])
  useEffect(() => {
    const resetInputs = () => { held.current.forEach((name) => send({ type: 'button', button: name, pressed: false })); held.current.clear(); setPressed(new Set()); send({ type: 'trigger', trigger: 'LT', value: 0 }); send({ type: 'trigger', trigger: 'RT', value: 0 }); send({ type: 'stick', stick: 'LEFT', x: 0, y: 0 }); send({ type: 'stick', stick: 'RIGHT', x: 0, y: 0 }); setTriggerValues({ LT: 0, RT: 0 }) }
    const wake = () => { if (document.visibilityState === 'visible' && 'wakeLock' in navigator) navigator.wakeLock?.request('screen').then((lock) => { wakeLock.current = lock }).catch(() => { }) }
    window.addEventListener('blur', resetInputs); document.addEventListener('visibilitychange', wake); return () => { window.removeEventListener('blur', resetInputs); document.removeEventListener('visibilitychange', wake) }
  }, [send])
  const toggleFullscreen = async () => { if (document.fullscreenElement) await document.exitFullscreen(); else await document.documentElement.requestFullscreen?.(); setFullscreen(Boolean(document.fullscreenElement)) }
  const trigger = (name: 'LT' | 'RT', value: number) => { setTriggerValues((current) => ({ ...current, [name]: value })); send({ type: 'trigger', trigger: name, value }) }
  const stick = (name: 'LEFT' | 'RIGHT', x: number, y: number) => send({ type: 'stick', stick: name, x, y })

  return <main className={`controller ${editing ? 'layout-editing' : ''}`} aria-label="MobileKonekt gamepad">
    <header className="topbar"><div className="brand"><span className="brand-mark" aria-hidden="true">✦</span><span>Mobile<span className="brand-accent">Konekt</span></span></div><div className={`connection ${connection}`} role="status"><span className="status-dot" />{error || (connection === 'connected' ? `Player ${player ?? '—'} connected` : connection === 'reconnecting' ? 'Reconnecting…' : 'Connecting…')}</div><div className="toolbar"><button className={`tool-button ${haptics ? 'active' : ''}`} aria-pressed={haptics} onClick={() => setHaptics((value) => !value)}><span aria-hidden="true">⌁</span><span className="tool-label">Haptics</span></button><button className="tool-button" aria-pressed={fullscreen} onClick={() => void toggleFullscreen()}><span aria-hidden="true">{fullscreen ? '⤢' : '⛶'}</span><span className="tool-label">Fullscreen</span></button>{editing ? <><select className="preset-select" aria-label="Layout preset" defaultValue="" onChange={(event) => applyPreset(event.target.value)}><option value="" disabled>Preset…</option>{PRESETS.map((preset) => <option key={preset.id} value={preset.id}>{preset.name}</option>)}</select><button className="tool-button" onClick={reset}>Reset</button><button className="tool-button save-button" onClick={save}>Save / Exit</button></> : <button className="tool-button edit-button" onClick={startEditing}>Edit layout</button>}</div></header>
    <section className="deck">{([
      ['lt', <Trigger name="LT" value={triggerValues.LT} onValue={(value) => trigger('LT', value)} />], ['lb', <GameButton name="LB" label="LB" pressed={pressed.has('LB')} onChange={setButton} />], ['dpad', <Dpad onChange={setButton} pressed={pressed} />], ['left-stick', <Stick name="LEFT" label="L" onMove={(x, y) => stick('LEFT', x, y)} />], ['ls', <GameButton name="LS" label="LS" pressed={pressed.has('LS')} onChange={setButton} />], ['select', <GameButton name="SELECT" label="SELECT" pressed={pressed.has('SELECT')} onChange={setButton} />], ['start', <GameButton name="START" label="START" pressed={pressed.has('START')} onChange={setButton} />], ['rb', <GameButton name="RB" label="RB" pressed={pressed.has('RB')} onChange={setButton} />], ['rt', <Trigger name="RT" value={triggerValues.RT} onValue={(value) => trigger('RT', value)} />], ['y', <GameButton name="Y" label="Y" pressed={pressed.has('Y')} onChange={setButton} />], ['x', <GameButton name="X" label="X" pressed={pressed.has('X')} onChange={setButton} />], ['b', <GameButton name="B" label="B" pressed={pressed.has('B')} onChange={setButton} />], ['a', <GameButton name="A" label="A" pressed={pressed.has('A')} onChange={setButton} />], ['rs', <GameButton name="RS" label="RS" pressed={pressed.has('RS')} onChange={setButton} />], ['right-stick', <Stick name="RIGHT" label="R" onMove={(x, y) => stick('RIGHT', x, y)} />],
    ] as const).map(([id, control]) => <LayoutControl key={id} id={id} point={layout[id]} editing={editing} onMove={move} className={['a', 'b', 'x', 'y'].includes(id) ? `face-button-control face-${id}` : ''}>{control}</LayoutControl>)}</section>
    <div className="rotate-hint"><span aria-hidden="true">↻</span> Rotate your device for the best experience</div>
  </main>
}

export default App
