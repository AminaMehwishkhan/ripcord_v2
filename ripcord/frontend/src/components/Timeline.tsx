import type { TimelineEvent } from "../types";

const KIND_DOT: Record<TimelineEvent["kind"], string> = {
  speech: "bg-sky-400", capture: "bg-blue-400", risk: "bg-amber-400", pause: "bg-rose-400",
  clarify: "bg-amber-300", verify: "bg-emerald-400", resume: "bg-emerald-400", action: "bg-cyan-300", system: "bg-white/40",
};

function fmtTs(ms: number): string {
  const total = Math.floor(ms / 1000);
  return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
}

export function Timeline({ events }: { events: TimelineEvent[] }) {
  if (events.length === 0) return <p className="text-sm text-dim">No events yet.</p>;
  return (
    <ol className="space-y-2 max-h-64 overflow-y-auto pr-1">
      {events.map((e, i) => (
        <li key={i} className="flex gap-3 text-sm rc-fade-in">
          <span className="mono text-xs text-faint pt-0.5 w-10 shrink-0">{fmtTs(e.ts_ms)}</span>
          <span className={`mt-1.5 h-1.5 w-1.5 rounded-full shrink-0 ${KIND_DOT[e.kind]}`} />
          <span className="flex-1">
            <span>{e.label}</span>
            {e.detail && <span className="block text-xs text-dim mt-0.5">{e.detail}</span>}
          </span>
        </li>
      ))}
    </ol>
  );
}
