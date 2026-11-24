import type { ResolvedEntry } from "../types";

export function SessionHistoryPanel({ current }: { current: ResolvedEntry[] }) {
  if (current.length === 0) return <p className="text-sm text-dim">Nothing resolved yet this call.</p>;
  return (
    <ul className="space-y-1.5 text-sm">
      {current.map((h, i) => (
        <li key={i} className="flex items-center justify-between">
          <span className="mono">{h.value}</span>
          <span className="flex items-center gap-2 text-xs">
            {h.required_clarification && <span className="chip chip-amber">asked once</span>}
            {h.risk_score !== null && <span className="text-dim">{Math.round(h.risk_score * 100)}% risk</span>}
            <span className={h.status === "VERIFIED" ? "chip chip-green" : "chip chip-grey"}>{h.status}</span>
          </span>
        </li>
      ))}
    </ul>
  );
}
