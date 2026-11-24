export const pct = (v: number, digits = 0) => `${(v * 100).toFixed(digits)}%`;

export function confTone(c: number): "ok" | "mid" | "low" {
  return c >= 0.85 ? "ok" : c >= 0.65 ? "mid" : "low";
}

export const TONE_COLOR = { ok: "var(--rc-green)", mid: "var(--rc-amber)", low: "var(--rc-red)" } as const;
