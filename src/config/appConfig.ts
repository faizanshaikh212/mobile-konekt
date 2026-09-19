export const APP_CONFIG = {
  name: "MobileKonekt",
  logoPath: "/mobilekonekt-logo.svg",
  tagline: "Remote gamepad",
  centerLabel: "MOBILEKONEKT",
  centerHint: "TOUCH CONTROLLER",
  controls: {
    lt: "LT",
    lb: "LB",
    dpad: "Directional pad",
    leftStick: "L",
    ls: "LS",
    select: "SELECT",
    start: "START",
    rb: "RB",
    rt: "RT",
    y: "Y",
    x: "X",
    b: "B",
    a: "A",
    rs: "RS",
    rightStick: "R",
    triggerSuffix: "analog trigger",
    stickSuffix: "analog stick",
  } satisfies Record<string, string>,
  status: {
    connected: (player: number | null) => `Player ${player ?? "—"} connected`,
    connecting: "Connecting…",
    reconnecting: "Reconnecting…",
  },
  toolbar: {
    haptics: "Haptics",
    fullscreen: "Fullscreen",
    edit: "Edit layout",
    preset: "Preset",
    reset: "Reset",
    save: "Save / Exit",
  },
  editing: {
    hint: "Drag controls to customize your layout",
  },
  rotateHint: "Rotate your device for the best experience",
  presets: {
    balanced: {
      label: "Balanced",
      description: "A comfortable all-round layout",
    },
    fps: { label: "FPS", description: "Aim and movement close to your thumbs" },
    racing: {
      label: "Racing",
      description: "Triggers and sticks are easy to reach",
    },
    retro: {
      label: "Retro",
      description: "Classic, simple two-hand arrangement",
    },
  },
} as const;

export type PresetId = keyof typeof APP_CONFIG.presets;
