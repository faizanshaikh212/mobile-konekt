const memory = new Map<string, string>();

function storage(): Storage | null {
  try {
    return typeof window !== "undefined" ? window.localStorage : null;
  } catch {
    return null;
  }
}

export function getStored(key: string): string | null {
  try {
    return storage()?.getItem(key) ?? memory.get(key) ?? null;
  } catch {
    return memory.get(key) ?? null;
  }
}

export function setStored(key: string, value: string): void {
  memory.set(key, value);
  try {
    storage()?.setItem(key, value);
  } catch {
    // Memory fallback keeps the current page usable when storage is blocked.
  }
}

export function makeDeviceToken(): string {
  const randomUuid = globalThis.crypto?.randomUUID;
  if (randomUuid) return randomUuid.call(globalThis.crypto);
  const random = () =>
    Math.floor(Math.random() * 0xffffffff)
      .toString(16)
      .padStart(8, "0");
  return `${random()}-${random()}-${Date.now().toString(16)}`;
}
