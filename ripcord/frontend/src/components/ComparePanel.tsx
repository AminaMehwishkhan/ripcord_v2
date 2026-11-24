import { Play } from "lucide-react";
import type { CompareState, Scenario, SessionState } from "../types";
import { ConversationView } from "./ConversationView";
import { DigitStrip } from "./DigitStrip";
import { Card } from "./ui";

function Outcome({ s, truth }: { s: SessionState; truth: string | null }) {
  if (s.escalated) {
    return <div className="chip chip-amber w-full justify-center py-2">Escalated to a human — no wrong action taken</div>;
  }
  if (s.action_result && s.verified_value) {
    const ok = truth ? s.verified_value === truth : null;
    if (ok === false) {
      return (
        <div className="chip chip-red w-full justify-center py-2 text-sm">
          ✕ Acted on {s.verified_value} — WRONG order (caller said {truth})
        </div>
      );
    }
    return (
      <div className="chip chip-green w-full justify-center py-2 text-sm">
        ✓ Acted on {s.verified_value}{ok ? " — correct" : ""}
      </div>
    );
  }
  if (s.clarification) return <div className="chip chip-amber w-full justify-center py-2">⏸ Paused — asking the caller</div>;
  return <div className="chip chip-grey w-full justify-center py-2">Waiting…</div>;
}

function Side({ title, tone, s, truth }: { title: string; tone: "red" | "cyan"; s: SessionState | null; truth: string | null }) {
  return (
    <Card
      title={title}
      right={<span className={`chip ${tone === "red" ? "chip-red" : "chip-green"}`}>{tone === "red" ? "no checks" : "Ripcord ON"}</span>}
    >
      <div className="space-y-4">
        <ConversationView turns={s?.conversation ?? []} maxHeight={250} empty="Press “Run both” to start." />
        <DigitStrip entity={s?.entity ?? null} risk={s?.risk} truth={truth} compact unchecked={s ? !s.ripcord_enabled : false} />
        {s && <Outcome s={s} truth={truth} />}
      </div>
    </Card>
  );
}

export function ComparePanel({ compare, scenarios, selected, onSelect, onRun }: {
  compare: CompareState | null;
  scenarios: Scenario[];
  selected: number;
  onSelect: (id: number) => void;
  onRun: () => void;
}) {
  const truth = compare?.truth ?? scenarios.find((s) => s.id === selected)?.truth ?? null;
  return (
    <div className="space-y-5">
      <Card>
        <div className="flex flex-col md:flex-row md:items-center gap-3">
          <select className="field flex-1" value={selected} onChange={(e) => onSelect(Number(e.target.value))} aria-label="Scenario">
            {scenarios.map((s) => (
              <option key={s.id} value={s.id}>{s.title}</option>
            ))}
          </select>
          <button className="btn btn-primary" onClick={onRun}><Play size={15} /> Run both</button>
        </div>
        {truth && (
          <p className="text-sm text-dim mt-3">
            The caller actually said: <span className="mono text-[var(--rc-text)] tracking-widest">{truth.split("").join(" ")}</span>
            <span className="text-faint"> · the same recorded audio goes into both agents</span>
          </p>
        )}
      </Card>
      <div className="grid lg:grid-cols-2 gap-5">
        <Side title="Plain voice agent" tone="red" s={compare?.a ?? null} truth={truth} />
        <Side title="Voice agent + Ripcord" tone="cyan" s={compare?.b ?? null} truth={truth} />
      </div>
    </div>
  );
}
