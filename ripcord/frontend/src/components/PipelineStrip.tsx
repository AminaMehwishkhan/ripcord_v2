import { Ear, ShieldCheck, Lock, Zap } from "lucide-react";
import type { SessionState } from "../types";

type Stage = "idle" | "active" | "warn" | "done" | "fail";

const STYLE: Record<Stage, string> = {
  idle: "border-[var(--rc-border)] text-faint",
  active: "border-[var(--rc-blue)] text-[var(--rc-blue)]",
  warn: "border-[var(--rc-amber)] text-[var(--rc-amber)]",
  done: "border-[var(--rc-green)] text-[var(--rc-green)]",
  fail: "border-[var(--rc-red)] text-[var(--rc-red)]",
};

export function PipelineStrip({ state }: { state: SessionState | null }) {
  const s = state;
  const hear: Stage = s?.entity ? "done" : "idle";
  const check: Stage = !s?.ripcord_enabled ? "idle" : s?.risk ? (s.risk.should_clarify ? "warn" : "done") : "idle";
  const guard: Stage = s?.escalated ? "fail" : s?.clarification ? "warn" : s?.verified_value ? "done" : "idle";
  const act: Stage = s?.escalated ? "fail" : s?.action_result ? "done" : "idle";
  const steps = [
    { name: "Hear", sub: "capture number", icon: Ear, stage: hear },
    { name: "Check", sub: s?.ripcord_enabled === false ? "skipped (OFF)" : "score the risk", icon: ShieldCheck, stage: check },
    { name: "Guard", sub: guard === "warn" ? "waiting on caller" : "must be VERIFIED", icon: Lock, stage: guard },
    { name: "Act", sub: act === "fail" ? "handed to a human" : "run the workflow", icon: Zap, stage: act },
  ];
  return (
    <ol className="grid grid-cols-4 gap-2" aria-label="Pipeline">
      {steps.map(({ name, sub, icon: Icon, stage }, i) => (
        <li key={name} className={`relative rounded-xl border px-3 py-2.5 bg-[#0a1120] transition-colors ${STYLE[stage]}`}>
          <div className="flex items-center gap-2">
            <Icon size={16} aria-hidden />
            <span className="text-sm font-semibold text-[var(--rc-text)]">{name}</span>
          </div>
          <div className="text-[11px] mt-0.5 opacity-90">{sub}</div>
          {i < steps.length - 1 && <span className="hidden md:block absolute -right-2.5 top-1/2 -translate-y-1/2 text-faint text-xs">›</span>}
        </li>
      ))}
    </ol>
  );
}
