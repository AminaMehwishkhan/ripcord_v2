import type { CriticalEntity, RiskAssessment } from "../types";
import { StatusBadge } from "./StatusBadge";
import { TONE_COLOR, confTone, pct } from "../lib/format";

/**
 * The captured number, one cell per digit, each with the recogniser's own
 * confidence underneath. Digits Ripcord is least sure about are ringed in amber;
 * when the true value is known (compare view / tests) a wrong digit turns red.
 */
export function DigitStrip({ entity, risk, truth, compact = false, unchecked = false }: {
  entity: CriticalEntity | null;
  risk?: RiskAssessment | null;
  truth?: string | null;
  compact?: boolean;
  unchecked?: boolean;
}) {
  if (!entity) {
    return <p className="text-dim text-sm">No number captured yet.</p>;
  }
  const weak = new Set(risk?.weak_positions ?? []);
  const verified = entity.status === "VERIFIED" && !unchecked;
  return (
    <div>
      <div className="flex flex-wrap items-end gap-2.5" aria-label={`Captured number ${entity.value}`}>
        {entity.value.split("").map((d, i) => {
          const c = entity.digit_confidences[i] ?? entity.confidence;
          const wrong = truth ? truth[i] !== d : false;
          const cls = wrong ? "digit-bad" : weak.has(i) ? "digit-weak" : verified ? "digit-ok" : "";
          return (
            <div key={i} className="flex flex-col items-center gap-1.5">
              <div className={`digit mono ${cls}`} style={compact ? { width: 44, height: 56, fontSize: 26 } : undefined}>
                {d}
                {weak.has(i) && !wrong && (
                  <span className="absolute -top-2 -right-2 h-5 w-5 rounded-full bg-amber-400 text-[#1b1200] text-xs font-bold flex items-center justify-center">?</span>
                )}
              </div>
              <div className="h-1.5 w-full rounded-full bg-white/5 overflow-hidden" title={`confidence ${pct(c)}`}>
                <div className="h-full rounded-full" style={{ width: pct(c), background: TONE_COLOR[confTone(c)] }} />
              </div>
              <span className="text-[11px] mono text-dim">{pct(c)}</span>
            </div>
          );
        })}
      </div>
      <div className="flex flex-wrap items-center gap-2 mt-3">
        {unchecked ? <span className="chip chip-grey">accepted without checking</span> : entity.status !== "UNKNOWN" && <StatusBadge status={entity.status} />}
        {!entity.format_valid && <span className="chip chip-red">expected 4 digits, heard {entity.value.length}</span>}
        {entity.style !== "digits" && entity.style !== "numeral" && (
          <span className="chip chip-grey">said as {entity.style === "pairs" ? "pairs" : "one big number"}</span>
        )}
        {entity.homophone_digits > 0 && <span className="chip chip-amber">digit heard as a common word</span>}
      </div>
    </div>
  );
}
