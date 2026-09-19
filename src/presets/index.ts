import type { ControlId, Layout, Point } from '../types/controller'

export type LayoutPreset = { id: string; name: string; description: string; layout: Layout }

const base: Layout = {
  lt: { x: 8, y: 9 }, lb: { x: 25, y: 9 }, dpad: { x: 17, y: 51 },
  'left-stick': { x: 18, y: 84 }, ls: { x: 32, y: 84 }, select: { x: 44, y: 88 },
  start: { x: 56, y: 88 }, rb: { x: 75, y: 9 }, rt: { x: 92, y: 9 },
  y: { x: 83, y: 43 }, x: { x: 78, y: 51 }, b: { x: 88, y: 51 }, a: { x: 83, y: 59 },
  rs: { x: 68, y: 84 }, 'right-stick': { x: 82, y: 84 },
}

const offset = (changes: Partial<Record<ControlId, Point>>): Layout => ({ ...base, ...changes })

export const PRESETS: LayoutPreset[] = [
  { id: 'balanced', name: 'Balanced', description: 'A comfortable all-round layout', layout: base },
  { id: 'fps', name: 'FPS', description: 'Aim and movement close to your thumbs', layout: offset({ dpad: { x: 14, y: 68 }, 'left-stick': { x: 24, y: 79 }, y: { x: 85, y: 34 }, x: { x: 79, y: 42 }, b: { x: 91, y: 42 }, a: { x: 85, y: 50 }, 'right-stick': { x: 76, y: 78 }, rs: { x: 66, y: 78 } }) },
  { id: 'racing', name: 'Racing', description: 'Triggers and sticks are easy to reach', layout: offset({ lt: { x: 18, y: 12 }, lb: { x: 33, y: 12 }, rt: { x: 82, y: 12 }, rb: { x: 67, y: 12 }, dpad: { x: 12, y: 48 }, y: { x: 88, y: 40 }, x: { x: 82, y: 48 }, b: { x: 94, y: 48 }, a: { x: 88, y: 56 }, 'left-stick': { x: 29, y: 78 }, 'right-stick': { x: 71, y: 78 } }) },
  { id: 'retro', name: 'Retro', description: 'Classic, simple two-hand arrangement', layout: offset({ dpad: { x: 25, y: 48 }, y: { x: 75, y: 40 }, x: { x: 69, y: 48 }, b: { x: 81, y: 48 }, a: { x: 75, y: 56 }, 'left-stick': { x: 25, y: 80 }, 'right-stick': { x: 75, y: 80 }, ls: { x: 39, y: 80 }, rs: { x: 61, y: 80 } }) },
]

export const DEFAULT_LAYOUT = PRESETS[0].layout
