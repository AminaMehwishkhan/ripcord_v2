import type { EntityStatus } from "../types";

const STYLE: Record<EntityStatus, { cls: string; label: string }> = {
  UNKNOWN: { cls: "chip-grey", label: "—" },
  UNCERTAIN: { cls: "chip-amber", label: "⚠ UNCERTAIN" },
  CLARIFYING: { cls: "chip-amber", label: "⏸ ASKING THE CALLER" },
  VERIFIED: { cls: "chip-green", label: "✓ VERIFIED" },
  INVALIDATED: { cls: "chip-red", label: "✕ REJECTED" },
};

export function StatusBadge({ status }: { status: EntityStatus }) {
  const s = STYLE[status];
  return <span className={`chip ${s.cls}`}>{s.label}</span>;
}
