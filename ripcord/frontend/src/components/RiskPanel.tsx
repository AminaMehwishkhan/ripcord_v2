import type { RiskAssessment } from "../types";
import { pct } from "../lib/format";

const LEVEL_COLOR = { LOW: "var(--rc-green)", MEDIUM: "var(--rc-amber)", HIGH: "var(--rc-red)" } as const;

const LABEL: Record<string, string> = {
  tok_min: "Weakest number word",
  tok_mean: "Average confidence",
  low_frac: "Share of shaky words",
  context_conf: "Words around the number",
  len_dev: "Wrong digit count",
  pairs: "Said in pairs",
  cardinal: "Said as one big number",
  teen_ten: "Fifteen / fifty confusion",
  homophones: "Digit heard as a word",
  no_carrier: "No “order number” phrase",
  competing: "Several numbers in turn",
  rate: "Speaking speed",
  contradiction: "Contradicts earlier number",
  correction_language: "Caller said “no / I said…”",
  repetition: "Caller repeated the number",
};

/** Probability bar with the "ask" threshold marked, plus per-feature contributions. */
export function RiskPanel({ risk, ripcordEnabled = true }: { risk: RiskAssessment | null; ripcordEnabled?: boolean }) {
  if (!risk) {
    return (
      <p className="text-dim text-sm">
        {ripcordEnabled ? "No assessment yet — waiting for a number." : "Ripcord is OFF: nothing is being checked."}
      </p>
    );
  }
  const color = LEVEL_COLOR[risk.risk_level];
  const rows = Object.entries(risk.breakdown)
    .filter(([, v]) => Math.abs(v) >= 0.05)
    .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
    .slice(0, 7);
  const maxAbs = Math.max(1, ...rows.map(([, v]) => Math.abs(v)));

  return (
    <div className="space-y-4">
      <div>
        <div className="flex items-baseline justify-between mb-1.5">
          <span className="text-sm text-dim">Chance this number is wrong</span>
          <span className="text-2xl font-bold mono" style={{ color }}>{pct(risk.risk_score)}</span>
        </div>
        <div className="relative h-3 rounded-full bg-white/5">
          <div className="h-full rounded-full transition-all duration-500" style={{ width: pct(Math.min(1, risk.risk_score)), background: color }} />
          <div className="absolute -top-1 -bottom-1 w-0.5 bg-white/80 rounded" style={{ left: pct(risk.threshold) }} title={`Ask below this line: ${pct(risk.threshold)}`} />
        </div>
        <div className="flex justify-between text-[11px] text-faint mt-1">
          <span>0%</span>
          <span>▲ asks a question above {pct(risk.threshold)}</span>
          <span>100%</span>
        </div>
      </div>

      <div className={`rounded-xl px-3 py-2 text-sm font-semibold ${risk.should_clarify ? "chip-amber" : "chip-green"}`} style={{ borderWidth: 1, borderStyle: "solid" }}>
        {risk.should_clarify ? "⏸ Pause and ask the caller" : "✓ Safe to proceed"}
      </div>

      {risk.reasons.length > 0 && (
        <ul className="space-y-1 text-sm">
          {risk.reasons.slice(0, 4).map((r) => (
            <li key={r} className="flex gap-2"><span className="text-amber-300">•</span><span>{r}</span></li>
          ))}
        </ul>
      )}

      {rows.length > 0 && (
        <div>
          <p className="card-title mb-2">Why — pushes toward “wrong” (→) or “fine” (←)</p>
          <div className="space-y-1.5">
            {rows.map(([k, v]) => (
              <div key={k} className="grid grid-cols-[150px_1fr_44px] items-center gap-2 text-xs">
                <span className="text-dim truncate" title={LABEL[k] ?? k}>{LABEL[k] ?? k}</span>
                <div className="relative h-2 rounded bg-white/5">
                  <div className="absolute top-0 bottom-0 left-1/2 w-px bg-white/20" />
                  <div
                    className="absolute top-0 bottom-0 rounded"
                    style={{
                      width: `${(Math.abs(v) / maxAbs) * 50}%`,
                      left: v >= 0 ? "50%" : `${50 - (Math.abs(v) / maxAbs) * 50}%`,
                      background: v >= 0 ? "var(--rc-red)" : "var(--rc-green)",
                    }}
                  />
                </div>
                <span className="mono text-right text-dim">{v > 0 ? "+" : ""}{v.toFixed(1)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
      <p className="text-[11px] text-faint">Engine: {risk.engine === "learned-v2" ? "learned evidence model" : "hand-weighted rules"}</p>
    </div>
  );
}
