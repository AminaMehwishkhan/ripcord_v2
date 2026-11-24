import { useEffect, useRef, useState } from "react";
import { assess } from "../services/api";
import type { AssessResponse } from "../types";
import { DigitStrip } from "./DigitStrip";
import { RiskPanel } from "./RiskPanel";
import { pct } from "../lib/format";
import { Card } from "./ui";

const PRESETS: Array<{ label: string; text: string; conf: number[] }> = [
  { label: "Clean capture", text: "my order number is one five eight zero", conf: [0.98, 0.97, 0.98, 0.99, 0.96, 0.95, 0.94, 0.95] },
  { label: "Heard 3 digits", text: "order number one five zero", conf: [0.95, 0.9, 0.55, 0.51, 0.48] },
  { label: "Big number, shaky", text: "my order number is one thousand five hundred eighty", conf: [0.98, 0.97, 0.98, 0.99, 0.5, 0.5, 0.45, 0.4, 0.5] },
  { label: "Pairs, shaky", text: "my order number is fifteen eighty", conf: [0.98, 0.97, 0.98, 0.99, 0.4, 0.35] },
  { label: "One shaky digit", text: "my order number is one five eight zero", conf: [0.98, 0.97, 0.98, 0.99, 0.96, 0.95, 0.52, 0.95] },
  { label: "Homophone", text: "order number three for seven two", conf: [0.95, 0.9, 0.93, 0.6, 0.92, 0.94] },
];

export function PlaygroundPanel() {
  const [text, setText] = useState(PRESETS[2].text);
  const [conf, setConf] = useState<number[]>(PRESETS[2].conf);
  const [res, setRes] = useState<AssessResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const words = text.trim().split(/\s+/).filter(Boolean);
  const confs = words.map((_, i) => conf[i] ?? 0.95);

  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      assess(text, words.map((w, i) => ({ text: w, confidence: confs[i] })))
        .then((r) => { setRes(r); setErr(null); })
        .catch(() => setErr("Backend not reachable."));
    }, 200);
    return () => { if (timer.current) clearTimeout(timer.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text, JSON.stringify(confs)]);

  return (
    <div className="space-y-5">
      <Card title="What-if playground" right={<span className="chip chip-blue">live — runs the real risk engine</span>}>
        <p className="text-sm text-dim mb-3">
          Type what the recogniser heard and drag each word's confidence. Watch how Ripcord's decision changes — this is the
          same code path as a live call. Try “One shaky digit”: with the model shipped here, a single weak digit on an
          otherwise clear number does <i>not</i> trigger a question, because for this recogniser that pattern turned out
          to be common on correct numbers (see the Benchmark tab). Wrong digit counts and shaky big numbers do.
        </p>
        <div className="flex flex-wrap gap-2 mb-3">
          {PRESETS.map((p) => (
            <button key={p.label} className="btn btn-sm" onClick={() => { setText(p.text); setConf(p.conf); }}>{p.label}</button>
          ))}
        </div>
        <input className="field mb-4" value={text} onChange={(e) => setText(e.target.value)} aria-label="Transcript" />
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
          {words.map((w, i) => (
            <div key={i} className="rounded-xl border border-[var(--rc-border)] bg-[#0a1120] p-2.5">
              <div className="flex items-center justify-between text-sm mb-1">
                <span className="font-semibold truncate">{w}</span>
                <span className="mono text-xs text-dim">{pct(confs[i])}</span>
              </div>
              <input
                type="range" min={5} max={100} value={Math.round(confs[i] * 100)} aria-label={`confidence of ${w}`}
                onChange={(e) => {
                  const next = [...confs];
                  next[i] = Number(e.target.value) / 100;
                  setConf(next);
                }}
              />
            </div>
          ))}
        </div>
        {err && <p className="text-rose-300 text-sm mt-3">{err}</p>}
      </Card>

      <div className="grid lg:grid-cols-2 gap-5">
        <Card title="Captured number">
          {res?.entity ? <DigitStrip entity={res.entity} risk={res.risk} /> : <p className="text-dim text-sm">No number found in that sentence.</p>}
          {res?.question && (
            <p className="mt-4 rounded-xl border border-[var(--rc-amber)]/40 bg-amber-400/5 p-3 text-[15px]">
              <span className="text-xs font-bold tracking-wider text-amber-300 block mb-1">RIPCORD WOULD ASK</span>
              “{res.question.question}”
            </p>
          )}
        </Card>
        <Card title="Decision">
          <RiskPanel risk={res?.risk ?? null} />
        </Card>
      </div>
    </div>
  );
}
