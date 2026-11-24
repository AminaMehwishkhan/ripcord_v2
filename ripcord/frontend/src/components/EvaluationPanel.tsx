import { useEffect, useState } from "react";
import { fetchEvaluation } from "../services/api";
import type { EvaluationReport } from "../types";

/** The 10 hand-written scripted scenarios, re-run through the pipeline. Illustrative only. */
export function EvaluationPanel() {
  const [report, setReport] = useState<EvaluationReport | null>(null);
  const [err, setErr] = useState(false);
  useEffect(() => {
    fetchEvaluation().then(setReport).catch(() => setErr(true));
  }, []);
  if (err) return <p className="text-sm text-rose-300">Could not reach the backend.</p>;
  if (!report) return <p className="text-sm text-dim">Running…</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-left text-dim border-b border-white/10">
            <th className="py-1.5 pr-3">#</th><th className="pr-3">Scenario</th><th className="pr-3">Plain agent</th>
            <th className="pr-3">With Ripcord</th><th className="pr-3">Truth</th><th>Asked?</th>
          </tr>
        </thead>
        <tbody>
          {report.per_scenario.map((s) => (
            <tr key={s.id} className="border-b border-white/5">
              <td className="py-1.5 pr-3">{s.id}</td>
              <td className="pr-3">{s.title}</td>
              <td className={`pr-3 mono ${s.mode_a_wrong ? "text-rose-300" : ""}`}>{s.mode_a_value ?? "—"}</td>
              <td className={`pr-3 mono ${s.mode_b_wrong ? "text-rose-300" : "text-emerald-300"}`}>{s.mode_b_value ?? "—"}</td>
              <td className="pr-3 mono text-dim">{s.ground_truth ?? "n/a"}</td>
              <td>{s.clarified ? "yes" : "no"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-[11px] text-faint mt-2">
        {report.entity_errors_without_ripcord} wrong without Ripcord → {report.entity_errors_with_ripcord} with it; {report.false_clarifications} unneeded questions.
        These 10 scripts are illustrative — the benchmark above is the real measurement.
      </p>
    </div>
  );
}
