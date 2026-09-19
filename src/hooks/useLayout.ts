import { useCallback, useState } from 'react'
import { DEFAULT_LAYOUT, PRESETS } from '../presets'
import type { ControlId, Layout, Point } from '../types/controller'

const STORAGE_KEY = 'mobilekonekt-controller-layout'
const clone = (layout: Layout): Layout => Object.fromEntries(Object.entries(layout).map(([id, point]) => [id, { ...point }])) as Layout

function readLayout(): Layout {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? 'null') as Partial<Layout> | null
    return saved ? { ...clone(DEFAULT_LAYOUT), ...saved } : clone(DEFAULT_LAYOUT)
  } catch { return clone(DEFAULT_LAYOUT) }
}

export function useLayout() {
  const [layout, setLayout] = useState<Layout>(readLayout)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState<Layout>(layout)
  const startEditing = useCallback(() => { setDraft(clone(layout)); setEditing(true) }, [layout])
  const save = useCallback(() => { localStorage.setItem(STORAGE_KEY, JSON.stringify(draft)); setLayout(clone(draft)); setEditing(false) }, [draft])
  const reset = useCallback(() => setDraft(clone(DEFAULT_LAYOUT)), [])
  const applyPreset = useCallback((id: string) => {
    const preset = PRESETS.find((item) => item.id === id)
    if (preset) setDraft(clone(preset.layout))
  }, [])
  const move = useCallback((id: ControlId, point: Point) => setDraft((current) => ({ ...current, [id]: point })), [])
  return { layout: editing ? draft : layout, editing, startEditing, save, reset, applyPreset, move }
}
