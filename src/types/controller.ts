export type Connection = "connecting" | "connected" | "reconnecting" | "error";
export type ButtonName =
  "A" | "B" | "X" | "Y" | "LB" | "RB" | "LS" | "RS" | "SELECT" | "START";
export type Direction = "UP" | "DOWN" | "LEFT" | "RIGHT";
export type TriggerName = "LT" | "RT";
export type StickName = "LEFT" | "RIGHT";

export type ControlId =
  | "lt"
  | "lb"
  | "dpad"
  | "left-stick"
  | "ls"
  | "select"
  | "start"
  | "rb"
  | "rt"
  | "a"
  | "b"
  | "x"
  | "y"
  | "rs"
  | "right-stick";

export type Point = { x: number; y: number };
export type Layout = Record<ControlId, Point>;
