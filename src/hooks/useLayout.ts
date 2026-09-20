import { useCallback, useState } from "react";
import { DEFAULT_LAYOUT, PRESETS } from "../presets";
import type { ControlId, Layout, Point } from "../types/controller";
import { getStored, setStored } from "../lib/browserStorage";

const STORAGE_KEY = "mobilekonekt-controller-layout-v4";
const clone = (layout: Layout): Layout =>
  Object.fromEntries(
    Object.entries(layout).map(([id, point]) => [
      id,
      { ...point, scale: point.scale ?? 1 },
    ]),
  ) as Layout;

function readLayout(): Layout {
  try {
    const saved = JSON.parse(
      getStored(STORAGE_KEY) ?? "null",
    ) as Partial<Layout> | null;
    return saved
      ? { ...clone(DEFAULT_LAYOUT), ...saved }
      : clone(DEFAULT_LAYOUT);
  } catch {
    return clone(DEFAULT_LAYOUT);
  }
}

export function useLayout(onSave?: (layout: Layout) => void) {
  const [layout, setLayout] = useState<Layout>(readLayout);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<Layout>(layout);
  const startEditing = useCallback(() => {
    setDraft(clone(layout));
    setEditing(true);
  }, [layout]);
  const save = useCallback(() => {
    setStored(STORAGE_KEY, JSON.stringify(draft));
    setLayout(clone(draft));
    setEditing(false);
    onSave?.(draft);
  }, [draft, onSave]);
  const applyRemote = useCallback((value: Partial<Layout>) => {
    const next = { ...clone(DEFAULT_LAYOUT), ...value };
    setStored(STORAGE_KEY, JSON.stringify(next));
    setLayout(next);
    setDraft(next);
  }, []);
  const applyLayout = useCallback((value: Layout) => {
    const next = { ...clone(DEFAULT_LAYOUT), ...value };
    setStored(STORAGE_KEY, JSON.stringify(next));
    setLayout(next);
    setDraft(next);
    setEditing(false);
    onSave?.(next);
  }, [onSave]);
  const reset = useCallback(() => setDraft(clone(DEFAULT_LAYOUT)), []);
  const applyPreset = useCallback((id: string) => {
    const preset = PRESETS.find((item) => item.id === id);
    if (preset) setDraft(clone(preset.layout));
  }, []);
  const move = useCallback(
    (id: ControlId, point: Point) =>
      setDraft((current) => ({
        ...current,
        [id]: { ...current[id], ...point },
      })),
    [],
  );
  const resize = useCallback(
    (id: ControlId, scale: number) =>
      setDraft((current) => ({
        ...current,
        [id]: { ...current[id], scale },
      })),
    [],
  );
  return {
    layout: editing ? draft : layout,
    editing,
    startEditing,
    save,
    reset,
    applyPreset,
    move,
    resize,
    applyRemote,
    applyLayout,
  };
}
