import type { ControlId, Layout, Point } from "../types/controller";

export type LayoutPreset = { id: string; layout: Layout };

const base: Layout = {
  lt: { x: 9, y: 9 },
  lb: { x: 24, y: 9 },
  dpad: { x: 17, y: 38 },
  "left-stick": { x: 18, y: 80 },
  ls: { x: 30, y: 80 },
  select: { x: 46, y: 91 },
  start: { x: 54, y: 91 },
  rb: { x: 76, y: 9 },
  rt: { x: 91, y: 9 },
  y: { x: 84, y: 29 },
  x: { x: 77, y: 41 },
  b: { x: 91, y: 41 },
  a: { x: 84, y: 53 },
  rs: { x: 69, y: 80 },
  "right-stick": { x: 82, y: 80 },
};

const offset = (changes: Partial<Record<ControlId, Point>>): Layout => ({
  ...base,
  ...changes,
});

export const PRESETS: LayoutPreset[] = [
  { id: "balanced", layout: base },
  {
    id: "fps",
    layout: offset({
      dpad: { x: 16, y: 39 },
      "left-stick": { x: 24, y: 80 },
      y: { x: 85, y: 29 },
      x: { x: 77, y: 41 },
      b: { x: 93, y: 41 },
      a: { x: 85, y: 53 },
      "right-stick": { x: 76, y: 80 },
      rs: { x: 66, y: 80 },
    }),
  },
  {
    id: "racing",
    layout: offset({
      lt: { x: 17, y: 9 },
      lb: { x: 31, y: 9 },
      rt: { x: 83, y: 9 },
      rb: { x: 69, y: 9 },
      dpad: { x: 14, y: 38 },
      y: { x: 88, y: 29 },
      x: { x: 80, y: 41 },
      b: { x: 96, y: 41 },
      a: { x: 88, y: 53 },
      "left-stick": { x: 27, y: 80 },
      "right-stick": { x: 73, y: 80 },
    }),
  },
  {
    id: "retro",
    layout: offset({
      dpad: { x: 26, y: 38 },
      y: { x: 74, y: 29 },
      x: { x: 66, y: 41 },
      b: { x: 82, y: 41 },
      a: { x: 74, y: 53 },
      "left-stick": { x: 27, y: 80 },
      "right-stick": { x: 73, y: 80 },
      ls: { x: 39, y: 80 },
      rs: { x: 61, y: 80 },
    }),
  },
];

export const DEFAULT_LAYOUT = PRESETS[0].layout;
