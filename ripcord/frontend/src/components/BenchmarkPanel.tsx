import { useEffect, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, ErrorBar, Legend, Line, LineChart, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { fetchBenchmark } from "../services/api";
import type { BenchmarkResults, PolicyResult, Rate } from "../types";
import { EvaluationPanel } from "./EvaluationPanel";
import { pct } from "../lib/format";
import { Card } from "./ui";

const ORDER = ["no_check", "always_confirm", "asr_mean_conf", "asr_min_conf", "ripcord_v1_rules", "ripcord_v2"];
const SHORT: Record<string, string> = {
  no_check: "No check", always_confirm: "Always read back", asr_mean_conf: "ASR confidence",
  asr_min_conf: "Weakest digit", ripcord_v1_rules: "Ripcord v1", ripcord_v2: "Ripcord v2",
};
const COLOR: Record<string, string> = {
  no_check: "#fb7185", always_confirm: "#a78bfa", asr_mean_conf: "#fbbf24",
  asr_min_conf: "#f59e0b", ripcord_v1_rules: "#5b8cff", ripcord_v2: "#3ee0d3",
};
const FEATURE_LABEL: Record<string, string> = {
  tok_min: "weakest word conf.", tok_mean: "mean conf.", low_frac: "share of shaky words",
  context_conf: "context conf.", len_dev: "wrong digit count", pairs: "said in pairs",
  cardinal: "said as one number", teen_ten: "fifteen/fifty word", homophones: "digit heard as word",
  no_carrier: "no 'order number'", competing: "several numbers", rate: "speaking speed",
};
const tip = { background: "#0d1424", border: "1px solid #2c3d62", borderRadius: 10, color: "#e8eefc", fontSize: 12 };
const axis = { fill: "#93a3c7", fontSize: 11 };

const rateText = (r: Rate | null | undefined) => (r ? pct(r.value, 1) : "—");
const ciText = (r: Rate | null | undefined) => (r ? `${pct(r.ci[0], 1)}–${pct(r.ci[1], 1)}` : "");

function Stat({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone: string }) {
  return (
    <div className="card card-pad">
      <div className="text-3xl font-bold mono" style={{ color: tone }}>{value}</div>
      <div className="text-sm mt-1">{label}</div>
      {sub && <div className="text-xs text-dim mt-0.5">{sub}</div>}
    </div>
  );
}

export function BenchmarkPanel() {
  const [data, setData] = useState<BenchmarkResults | null | undefined>(undefined);
  useEffect(() => {
    fetchBenchmark().then(setData).catch(() => setData(null));
  }, []);

  if (data === undefined) return <p className="text-dim">Loading benchmark…</p>;
  if (data === null) {
    return (
      <Card title="Benchmark">
        <p className="text-dim text-sm">
          No results yet. Build the data and score it with <span className="mono">benchmark/build_dataset.py</span>,{" "}
          <span className="mono">train_risk_model.py</span> and <span className="mono">evaluate.py</span>.
        </p>
      </Card>
    );
  }

  const p = data.policies;
  const v2: PolicyResult | undefined = p.ripcord_v2;
  const base = p.no_check;

  const barData = ORDER.filter((k) => p[k]).map((k) => {
    const r = p[k].wrong_action;
    return { key: k, name: SHORT[k], value: +(r.value * 100).toFixed(2), err: [+((r.value - r.ci[0]) * 100).toFixed(2), +((r.ci[1] - r.value) * 100).toFixed(2)] };
  });

  const curveKeys = ["ripcord_v2", "ripcord_v1_rules", "asr_mean_conf", "asr_min_conf"].filter((k) => data.curves[k]);
  const xs = Array.from(new Set(curveKeys.flatMap((k) => data.curves[k].map((c) => c.false_alarm)))).sort((a, b) => a - b);
  const curveData = xs.map((x) => {
    const row: Record<string, number> = { x: +(x * 100).toFixed(1) };
    for (const k of curveKeys) {
      const pts = data.curves[k].filter((c) => c.false_alarm <= x);
      row[k] = +(Math.max(0, ...pts.map((c) => c.catch)) * 100).toFixed(1);
    }
    return row;
  });

  const condData = Object.entries(data.by_condition).map(([k, c]) => ({
    key: k, name: c.label.replace(/ \(.*\)/, ""), full: c.label, n: c.n,
    plain: +((c.no_check?.wrong_action ?? 0) * 100).toFixed(1),
    ripcord: +((c.ripcord_v2?.wrong_action ?? 0) * 100).toFixed(1),
    asked: +((c.ripcord_v2?.asked ?? 0) * 100).toFixed(1),
  }));

  const wData = data.model.features
    .map((f, i) => ({ name: FEATURE_LABEL[f] ?? f, w: +data.model.weights[i].toFixed(2) }))
    .filter((d) => Math.abs(d.w) > 0.01)
    .sort((a, b) => Math.abs(b.w) - Math.abs(a.w));

  return (
    <div className="space-y-5">
      <Card>
        <div className="flex flex-wrap items-center gap-2 mb-2">
          <span className="chip chip-blue">Held-out test set</span>
          <span className="text-sm text-dim">
            {data.n_calls} calls · voices and order numbers never seen in training · scored {data.generated}
          </span>
        </div>
        <p className="text-sm text-dim">
          Speech is synthetic (VCTK voices), degraded with noise, babble, phone-line and echo, then transcribed by a real
          streaming recogniser whose per-word confidences are genuine. In this data the recogniser alone gets{" "}
          <b className="text-[var(--rc-text)]">{pct(data.capture_error_rate ?? 0, 0)}</b> of order numbers wrong, so absolute rates
          are harsher than a premium recogniser would give — the comparison between systems is the point.
        </p>
      </Card>

      {v2 && base && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <Stat label="Wrong numbers acted on" tone="var(--rc-cyan)" value={rateText(v2.wrong_action)}
            sub={`plain agent: ${rateText(base.wrong_action)} · 95% CI ${ciText(v2.wrong_action)}`} />
          <Stat label="Calls resolved correctly" tone="var(--rc-green)" value={rateText(v2.correct_action)}
            sub={`plain agent: ${rateText(base.correct_action)} · still waiting after one reply: ${rateText(v2.unresolved)}`} />
          <Stat label="Mishearings caught" tone="var(--rc-blue)" value={rateText(v2.error_catch_rate)}
            sub={`of ${v2.misheard_calls} misheard calls — mostly wrong digit counts`} />
          <Stat label="Unneeded questions" tone="var(--rc-amber)" value={rateText(v2.false_alarm_rate)}
            sub={`of ${v2.clean_capture_calls} correctly heard calls · ${v2.questions_per_call.value.toFixed(2)} questions per call`} />
        </div>
      )}

      {v2 && (
        <Card title="Reading these numbers honestly">
          <ul className="text-sm text-dim space-y-1.5 list-disc pl-5">
            <li>
              Most of this recogniser's mistakes drop or garble digits, so the capture is not 4 digits long. Every system
              below that checks the digit count and asks a question catches them, so the simple baselines land close to
              Ripcord on wrong actions. The learned model's edge shows in fewer needless questions than v1 and in the
              hard case below.
            </li>
            <li>
              “Still waiting” calls are safe, not wrong: the benchmark replays only one caller reply, so a call whose
              reply is also misheard is left open. A live agent would ask again or hand over.
            </li>
          </ul>
        </Card>
      )}

      <div className="grid lg:grid-cols-2 gap-5">
        <Card title="Wrong numbers acted on — lower is better">
          <div style={{ height: 290 }}>
            <ResponsiveContainer>
              <BarChart data={barData} margin={{ top: 10, right: 10, left: -10, bottom: 18 }}>
                <CartesianGrid stroke="#1f2c47" vertical={false} />
                <XAxis dataKey="name" tick={axis} interval={0} angle={-18} textAnchor="end" height={50} />
                <YAxis tick={axis} unit="%" />
                <Tooltip contentStyle={tip} cursor={{ fill: "rgba(255,255,255,.04)" }} formatter={(v) => [`${v}%`, "wrong actions"]} />
                <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                  {barData.map((d) => <Cell key={d.key} fill={COLOR[d.key]} />)}
                  <ErrorBar dataKey="err" width={5} stroke="#e8eefc" strokeWidth={1.2} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <p className="text-[11px] text-faint">Whiskers are 95% bootstrap confidence intervals. Includes the caller's recorded reply to any question.</p>
        </Card>

        <Card title="Catch more mistakes for fewer needless questions">
          <div style={{ height: 290 }}>
            <ResponsiveContainer>
              <LineChart data={curveData} margin={{ top: 10, right: 12, left: -10, bottom: 18 }}>
                <CartesianGrid stroke="#1f2c47" />
                <XAxis dataKey="x" type="number" domain={[0, 100]} tick={axis} unit="%" label={{ value: "needless questions (false alarms)", position: "insideBottom", offset: -8, fill: "#93a3c7", fontSize: 11 }} />
                <YAxis tick={axis} unit="%" domain={[0, 100]} />
                <Tooltip contentStyle={tip} formatter={(v, n) => [`${v}%`, SHORT[String(n)] ?? String(n)]} labelFormatter={(l) => `false alarms ${l}%`} />
                <Legend formatter={(n) => SHORT[n] ?? n} wrapperStyle={{ fontSize: 12, paddingTop: 6 }} />
                {curveKeys.map((k) => (
                  <Line key={k} dataKey={k} type="stepAfter" stroke={COLOR[k]} strokeWidth={k === "ripcord_v2" ? 3 : 1.6} dot={false} />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
          <p className="text-[11px] text-faint">
            Higher and further left is better. AUROC — Ripcord v2: {data.auroc.ripcord_v2 ?? "—"}, ASR confidence: {data.auroc.asr_mean_conf ?? "—"}
            {data.auroc_valid_format ? ` · on 4-digit captures only: ${data.auroc_valid_format.ripcord_v2 ?? "—"} vs ${data.auroc_valid_format.asr_mean_conf ?? "—"}` : ""}.
          </p>
        </Card>
      </div>

      <div className="grid lg:grid-cols-2 gap-5">
        <Card title="By audio condition — wrong numbers acted on">
          <div style={{ height: 290 }}>
            <ResponsiveContainer>
              <BarChart data={condData} margin={{ top: 10, right: 10, left: -10, bottom: 24 }}>
                <CartesianGrid stroke="#1f2c47" vertical={false} />
                <XAxis dataKey="name" tick={axis} interval={0} angle={-20} textAnchor="end" height={56} />
                <YAxis tick={axis} unit="%" />
                <Tooltip contentStyle={tip} cursor={{ fill: "rgba(255,255,255,.04)" }} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="plain" name="Plain agent" fill="#fb7185" radius={[4, 4, 0, 0]} />
                <Bar dataKey="ripcord" name="With Ripcord" fill="#3ee0d3" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card title="What the model looks at">
          <div style={{ height: 290 }}>
            <ResponsiveContainer>
              <BarChart data={wData} layout="vertical" margin={{ top: 4, right: 14, left: 30, bottom: 4 }}>
                <CartesianGrid stroke="#1f2c47" horizontal={false} />
                <XAxis type="number" tick={axis} />
                <YAxis type="category" dataKey="name" tick={axis} width={130} />
                <Tooltip contentStyle={tip} cursor={{ fill: "rgba(255,255,255,.04)" }} />
                <ReferenceLine x={0} stroke="#62739a" />
                <Bar dataKey="w" name="weight (+ = riskier)" radius={3}>
                  {wData.map((d, i) => <Cell key={i} fill={d.w > 0 ? "#fb7185" : "#34d399"} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <p className="text-[11px] text-faint">Standardised logistic-regression weights: red raises the chance Ripcord asks, green lowers it.</p>
        </Card>
      </div>

      {data.hard_case && (() => {
        const hc = data.hard_case;
        const keys = ["ripcord_v2", "asr_mean_conf", "asr_min_conf"].filter((k) => hc.curves[k]);
        const xsH = Array.from(new Set(keys.flatMap((k) => hc.curves[k].map((c) => c.false_alarm)))).sort((a, b) => a - b);
        const rowsH = xsH.map((x) => {
          const row: Record<string, number> = { x: +(x * 100).toFixed(1), chance: +(x * 100).toFixed(1) };
          for (const k of keys) row[k] = +(Math.max(0, ...hc.curves[k].filter((c) => c.false_alarm <= x).map((c) => c.catch)) * 100).toFixed(1);
          return row;
        });
        return (
          <Card title="The hard case: wrong numbers that look normal"
            right={<span className="chip chip-grey">{hc.n_misheard} misheard of {hc.n} · train+val, cross-validated</span>}>
            <div className="grid lg:grid-cols-[1.4fr_1fr] gap-5 items-center">
              <div style={{ height: 250 }}>
                <ResponsiveContainer>
                  <LineChart data={rowsH} margin={{ top: 8, right: 12, left: -10, bottom: 22 }}>
                    <CartesianGrid stroke="#1f2c47" />
                    <XAxis dataKey="x" type="number" domain={[0, 100]} tick={axis} unit="%" label={{ value: "needless questions", position: "insideBottom", offset: -10, fill: "#93a3c7", fontSize: 11 }} />
                    <YAxis tick={axis} unit="%" domain={[0, 100]} />
                    <Tooltip contentStyle={tip} formatter={(v, n) => [`${v}%`, n === "chance" ? "coin flip" : SHORT[String(n)] ?? String(n)]} labelFormatter={(l) => `needless questions ${l}%`} />
                    <Legend verticalAlign="top" height={26} formatter={(n) => (n === "chance" ? "Coin flip" : SHORT[n] ?? n)} wrapperStyle={{ fontSize: 12 }} />
                    <Line dataKey="chance" stroke="#62739a" strokeDasharray="4 4" dot={false} strokeWidth={1.2} />
                    {keys.map((k) => <Line key={k} dataKey={k} type="stepAfter" stroke={COLOR[k]} strokeWidth={k === "ripcord_v2" ? 3 : 1.6} dot={false} />)}
                  </LineChart>
                </ResponsiveContainer>
              </div>
              <div className="text-sm text-dim space-y-2">
                <p>
                  Only captures that already look like a normal 4-digit number. Ranking quality (AUROC, 0.5 = coin flip):{" "}
                  <b className="text-[var(--rc-text)]">Ripcord v2 {hc.auroc.ripcord_v2}</b>, ASR confidence {hc.auroc.asr_mean_conf},
                  weakest digit {hc.auroc.asr_min_conf}.
                </p>
                <p>
                  For this recogniser its own confidence says almost nothing about these. How the number was said (as one big
                  number, in pairs) and how fast says more. The held-out test set has only {data.policies.ripcord_v2?.misheard_valid_format_calls ?? "a few"} such
                  cases, so this larger cross-validated sample is the better evidence.
                </p>
              </div>
            </div>
          </Card>
        );
      })()}

      {data.reliability && (
        <Card title="Is the percentage honest? (calibration)" right={<span className="chip chip-grey">ECE {data.reliability.ece}</span>}>
          <div style={{ height: 230 }}>
            <ResponsiveContainer>
              <LineChart data={data.reliability.bins.map((b) => ({ ...b, predicted: +(b.predicted * 100).toFixed(1), observed: +(b.observed * 100).toFixed(1) }))} margin={{ top: 10, right: 12, left: -10, bottom: 18 }}>
                <CartesianGrid stroke="#1f2c47" />
                <XAxis dataKey="predicted" type="number" domain={[0, 100]} tick={axis} unit="%" label={{ value: "what Ripcord said", position: "insideBottom", offset: -10, fill: "#93a3c7", fontSize: 11 }} />
                <YAxis tick={axis} unit="%" domain={[0, 100]} />
                <Tooltip
                  contentStyle={tip}
                  content={({ payload }) => {
                    const p = payload?.[0]?.payload as { predicted: number; observed: number; n: number } | undefined;
                    if (!p) return null;
                    return (
                      <div style={tip} className="px-3 py-2 text-xs">
                        <div>said {p.predicted}% likely wrong</div>
                        <div>actually wrong {p.observed}%</div>
                        <div className="text-faint">{p.n} calls in this bin</div>
                      </div>
                    );
                  }}
                />
                <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 100, y: 100 }]} stroke="#62739a" strokeDasharray="4 4" />
                <Line
                  dataKey="observed"
                  name="actually wrong"
                  stroke="none"
                  isAnimationActive={false}
                  dot={(p: { cx?: number; cy?: number; payload?: { n: number } }) => {
                    const n = p.payload?.n ?? 1;
                    const r = Math.min(9, 3 + Math.sqrt(n) * 0.5);
                    return <circle key={`${p.cx}-${p.cy}`} cx={p.cx} cy={p.cy} r={r} fill="#3ee0d3" fillOpacity={n < 10 ? 0.35 : 0.9} stroke="#3ee0d3" />;
                  }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <p className="text-[11px] text-faint">When Ripcord says “X% likely wrong”, a dot on the dashed diagonal means it was wrong X% of the time. Bigger dots = more calls; faint dots have fewer than 10 calls and are mostly noise.</p>
        </Card>
      )}

      <Card title="All systems, side by side">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-dim text-xs border-b border-white/10">
                <th className="py-2 pr-3">System</th><th className="pr-3">Wrong actions</th><th className="pr-3">Resolved correctly</th><th className="pr-3">Mishearings caught</th>
                <th className="pr-3">Needless questions</th><th className="pr-3">Questions / call</th><th>Still waiting</th>
              </tr>
            </thead>
            <tbody>
              {ORDER.filter((k) => p[k]).map((k) => (
                <tr key={k} className={`border-b border-white/5 ${k === "ripcord_v2" ? "bg-cyan-400/5" : ""}`}>
                  <td className="py-2 pr-3 font-semibold"><span className="inline-block h-2 w-2 rounded-full mr-2" style={{ background: COLOR[k] }} />{p[k].label}</td>
                  <td className="pr-3 mono">{rateText(p[k].wrong_action)} <span className="text-faint text-xs">{ciText(p[k].wrong_action)}</span></td>
                  <td className="pr-3 mono">{rateText(p[k].correct_action)}</td>
                  <td className="pr-3 mono">{rateText(p[k].error_catch_rate)}</td>
                  <td className="pr-3 mono">{rateText(p[k].false_alarm_rate)}</td>
                  <td className="pr-3 mono">{p[k].questions_per_call.value.toFixed(2)}</td>
                  <td className="mono">{rateText(p[k].unresolved)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card title="Where Ripcord still fails" right={<span className="chip chip-amber">{data.silent_failures.length} shown</span>}>
        {data.silent_failures.length === 0 ? (
          <p className="text-sm text-dim">No wrong action on this test set.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-dim border-b border-white/10">
                  <th className="py-1.5 pr-3">Condition</th><th className="pr-3">Truth</th><th className="pr-3">Acted on</th><th className="pr-3">Weakest conf.</th><th>Recogniser heard</th>
                </tr>
              </thead>
              <tbody>
                {data.silent_failures.map((f) => (
                  <tr key={f.id} className="border-b border-white/5">
                    <td className="py-1.5 pr-3">{f.condition}</td>
                    <td className="pr-3 mono">{f.truth}</td>
                    <td className="pr-3 mono text-rose-300">{f.heard ?? "—"}</td>
                    <td className="pr-3 mono">{f.min_conf != null ? pct(f.min_conf) : "—"}</td>
                    <td className="text-dim">{f.transcript}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="text-[11px] text-faint mt-2">
          These are wrong numbers that still look like a normal 4-digit order number — usually said as “… thousand … hundred …” or in pairs, where the recogniser merges or swaps words.
          Their confidence was not unusually low, so no confidence check could see them. Closing that gap needs a second signal: reading every number back, keypad entry, or a lookup that checks the number exists.
        </p>
      </Card>

      <details className="card card-pad">
        <summary className="cursor-pointer card-title">Scripted scenarios (illustrative, hand-written)</summary>
        <div className="mt-3"><EvaluationPanel /></div>
      </details>

      <Card title="Method and limits">
        <ul className="text-sm text-dim space-y-1.5 list-disc pl-5">
          <li>{data.dataset.total} calls ({data.dataset.per_split.train} train / {data.dataset.per_split.val} validation / {data.dataset.per_split.test} test), {data.dataset.speakers} voices; splits never share a voice or an order number.</li>
          <li>Recogniser: {data.dataset.asr}. Voices: {data.dataset.tts}. Not AssemblyAI — confidences from different engines are not interchangeable, so retrain on your own engine's output (<span className="mono">benchmark/README.md</span>).</li>
          <li>The model is fitted on captures that already look like a normal 4-digit number (the hard case). A wrong digit count is handled by a rate measured on the training data, because those are almost always wrong and easy to see.</li>
          <li>The threshold and regularisation were chosen by cross-validation on train+validation only; the test set was only scored after the model was fixed. It was scored again once after a bug fix (a wrong-length number could be confirmed by a garbled repeat); see docs/evaluation.md.</li>
          <li>A synthetic voice is not a human voice. Treat these as a controlled comparison, not a field accuracy claim.</li>
        </ul>
      </Card>
    </div>
  );
}
