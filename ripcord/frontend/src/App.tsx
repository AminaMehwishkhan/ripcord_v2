import { useEffect, useMemo, useRef, useState } from "react";
import { BarChart3, Columns2, Mic, Play, RotateCcw, SlidersHorizontal, Square, Activity } from "lucide-react";
import { useRipcordSession } from "./hooks/useRipcordSession";
import { useMicCapture } from "./hooks/useMicCapture";
import { fetchHealth, fetchScenarios } from "./services/api";
import type { ConnectionStatus, Health, Scenario } from "./types";
import { BenchmarkPanel } from "./components/BenchmarkPanel";
import { ComparePanel } from "./components/ComparePanel";
import { ConversationView } from "./components/ConversationView";
import { DigitStrip } from "./components/DigitStrip";
import { PipelineStrip } from "./components/PipelineStrip";
import { PlaygroundPanel } from "./components/PlaygroundPanel";
import { ReplyPanel } from "./components/ReplyPanel";
import { RiskPanel } from "./components/RiskPanel";
import { SessionHistoryPanel } from "./components/SessionHistoryPanel";
import { Timeline } from "./components/Timeline";
import { Waveform } from "./components/Waveform";
import { pct } from "./lib/format";
import { Card } from "./components/ui";

type Tab = "live" | "compare" | "benchmark" | "playground";

const TABS: Array<{ id: Tab; label: string; icon: typeof Activity }> = [
  { id: "live", label: "Live demo", icon: Activity },
  { id: "compare", label: "Side by side", icon: Columns2 },
  { id: "benchmark", label: "Benchmark", icon: BarChart3 },
  { id: "playground", label: "Playground", icon: SlidersHorizontal },
];

const CONNECTION: Record<ConnectionStatus, { text: string; color: string; pulse?: boolean }> = {
  idle: { text: "Idle", color: "bg-white/30" },
  connecting: { text: "Connecting…", color: "bg-amber-400", pulse: true },
  live: { text: "Connected", color: "bg-emerald-400" },
  reconnecting: { text: "Reconnecting…", color: "bg-amber-400", pulse: true },
  disconnected: { text: "Disconnected", color: "bg-rose-400" },
};

function ScenarioSelect({ scenarios, value, onChange }: { scenarios: Scenario[]; value: number; onChange: (id: number) => void }) {
  const rec = scenarios.filter((s) => s.source === "recorded");
  const scr = scenarios.filter((s) => s.source === "scripted");
  return (
    <select className="field" value={value} onChange={(e) => onChange(Number(e.target.value))} aria-label="Scenario">
      {rec.length > 0 && (
        <optgroup label="Recorded — real recogniser output">
          {rec.map((s) => <option key={s.id} value={s.id}>{s.title}</option>)}
        </optgroup>
      )}
      <optgroup label="Scripted — hand-written">
        {scr.map((s) => <option key={s.id} value={s.id}>{s.id}. {s.title}</option>)}
      </optgroup>
    </select>
  );
}

export default function App() {
  const session = useRipcordSession();
  const { connected, wsReconnecting, state, compare, systemMessage, errorMessage } = session;

  const [tab, setTab] = useState<Tab>("live");
  const [ripcordEnabled, setRipcordEnabled] = useState(true);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const started = useRef(false);
  const mic = useMicCapture((chunk) => session.sendAudio(chunk));

  useEffect(() => {
    fetchScenarios().then((s) => { setScenarios(s); setSelected((cur) => cur ?? s[0]?.id ?? null); }).catch(() => {});
    fetchHealth().then(setHealth).catch(() => {});
  }, []);

  useEffect(() => {
    if (connected && !started.current) {
      started.current = true;
      session.startSession(ripcordEnabled, true);
    }
  }, [connected, ripcordEnabled, session]);

  const scenario = useMemo(() => scenarios.find((s) => s.id === selected), [scenarios, selected]);

  const toggleRipcord = () => {
    const next = !ripcordEnabled;
    setRipcordEnabled(next);
    session.toggleRipcord(next);
  };
  const run = () => selected !== null && session.runMockScenario(selected, ripcordEnabled);
  const realMic = async () => {
    if (mic.capturing) { mic.stop(); session.stop(); }
    else { session.startRealStream(ripcordEnabled); await mic.start(); }
  };

  const realAvailable = Boolean(health?.assemblyai_key_configured && !health?.mock_mode);
  const connStatus: ConnectionStatus = !connected ? (wsReconnecting ? "reconnecting" : "disconnected") : state?.connection_status ?? "idle";
  const conn = CONNECTION[connStatus];

  return (
    <div className="min-h-screen max-w-[1240px] mx-auto px-4 md:px-8 py-6 md:py-8">
      <header className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 mb-6">
        <div className="flex items-center gap-3.5">
          <svg width="40" height="40" viewBox="0 0 40 40" aria-hidden>
            <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#3ee0d3" /><stop offset="1" stopColor="#5b8cff" /></linearGradient></defs>
            <rect width="40" height="40" rx="11" fill="#0d1424" stroke="url(#g)" strokeWidth="1.5" />
            <path d="M12 24 L17 17 L21 22 L28 12" fill="none" stroke="url(#g)" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
            <circle cx="28" cy="12" r="2.4" fill="#3ee0d3" />
          </svg>
          <div>
            <h1 className="text-2xl font-extrabold tracking-tight leading-none bg-gradient-to-r from-cyan-300 to-blue-400 bg-clip-text text-transparent">RIPCORD</h1>
            <p className="text-sm text-dim mt-1">Catch the misunderstanding before it becomes an action.</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2.5">
          <span className="chip chip-grey"><span className={`h-2 w-2 rounded-full ${conn.color} ${conn.pulse ? "rc-pulse" : ""}`} />{conn.text}</span>
          {health && <span className="chip chip-grey" title="Risk engine and the probability above which Ripcord asks a question">
            {health.risk_engine === "learned-v2" ? "learned model" : "rules"} · asks above {pct(health.clarify_threshold)}
          </span>}
          {state?.last_decision_latency_ms != null && <span className="chip chip-grey mono">{state.last_decision_latency_ms} ms</span>}
          <button onClick={toggleRipcord} className={`btn ${ripcordEnabled ? "btn-good" : ""}`} aria-pressed={ripcordEnabled}>
            Ripcord {ripcordEnabled ? "ON" : "OFF"}
          </button>
        </div>
      </header>

      <nav className="flex flex-wrap gap-1.5 mb-6 p-1 rounded-xl bg-[#0a1120] border border-[var(--rc-border)] w-fit" aria-label="Sections">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button key={id} onClick={() => setTab(id)} aria-current={tab === id}
            className={`inline-flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-sm font-semibold transition ${tab === id ? "bg-[#1a2742] text-white" : "text-dim hover:text-white"}`}>
            <Icon size={15} aria-hidden /> {label}
          </button>
        ))}
      </nav>

      {tab === "benchmark" && <BenchmarkPanel />}
      {tab === "playground" && <PlaygroundPanel />}
      {tab === "compare" && (
        <ComparePanel compare={compare} scenarios={scenarios} selected={selected ?? 0}
          onSelect={setSelected} onRun={() => selected !== null && session.runCompare(selected)} />
      )}

      {tab === "live" && (
        <div className="space-y-5">
          <Card>
            <div className="flex flex-col lg:flex-row gap-3 lg:items-center">
              <div className="flex-1 min-w-0"><ScenarioSelect scenarios={scenarios} value={selected ?? 0} onChange={setSelected} /></div>
              <div className="flex flex-wrap gap-2">
                <button className="btn btn-primary" onClick={run} disabled={selected === null}><Play size={15} /> Run scenario</button>
                <button className="btn" onClick={session.reset}><RotateCcw size={15} /> Reset</button>
                <button className="btn" onClick={realMic} disabled={!realAvailable}
                  title={realAvailable ? "" : "Set ASSEMBLYAI_API_KEY and MOCK_MODE=false on the backend to use your microphone"}>
                  {mic.capturing ? <><Square size={14} /> Stop mic</> : <><Mic size={15} /> Use real mic</>}
                </button>
              </div>
            </div>
            {scenario && (
              <p className="text-sm text-dim mt-3">
                {scenario.source === "recorded"
                  ? <>Recorded: a real recogniser's transcript and word confidences{scenario.condition ? ` (${scenario.condition})` : ""}. The caller said <span className="mono text-[var(--rc-text)] tracking-widest">{scenario.truth?.split("").join(" ")}</span>.</>
                  : "Scripted: hand-written transcript with illustrative confidences."}
              </p>
            )}
            {mic.capturing && <div className="mt-3"><Waveform level={mic.level} active={mic.capturing} /></div>}
          </Card>

          {(systemMessage || errorMessage || mic.error) && (
            <div className="text-sm space-y-1" role="status">
              {errorMessage && <p className="text-rose-300">{errorMessage}</p>}
              {mic.error && <p className="text-rose-300">{mic.error}</p>}
              {systemMessage && <p className="text-dim">{systemMessage}</p>}
            </div>
          )}

          <PipelineStrip state={state} />

          <div className="grid lg:grid-cols-12 gap-5">
            <div className="lg:col-span-7 space-y-5">
              <Card title="Conversation" right={state?.mock_mode ? <span className="chip chip-grey">replayed audio</span> : <span className="chip chip-green">live audio</span>}>
                <ConversationView turns={state?.conversation ?? []} empty="Pick a scenario and press Run." maxHeight={330} />
                {state && (state.clarification || state.escalated) && (
                  <div className="mt-4">
                    <ReplyPanel clarification={state.clarification} escalated={state.escalated} scenario={scenario}
                      onRecorded={session.recordedReply} onType={session.userResponse} />
                  </div>
                )}
                {state?.action_result && !state.escalated && (
                  <div className={`mt-4 rounded-xl border p-3.5 rc-fade-in ${scenario?.truth && state.verified_value && scenario.truth !== state.verified_value ? "border-[var(--rc-red)]/50 bg-rose-400/5" : "border-[var(--rc-green)]/40 bg-emerald-400/5"}`}>
                    <p className="text-xs font-bold tracking-wider" style={{ color: scenario?.truth && state.verified_value && scenario.truth !== state.verified_value ? "var(--rc-red)" : "var(--rc-green)" }}>ACTION TAKEN</p>
                    <p className="text-[17px] mt-0.5">{state.action_result}</p>
                    {scenario?.truth && state.verified_value && scenario.truth !== state.verified_value && (
                      <p className="text-sm text-rose-300 mt-1">That is the wrong order — the caller said {scenario.truth}.</p>
                    )}
                  </div>
                )}
              </Card>
              <Card title="Event timeline"><Timeline events={state?.timeline ?? []} /></Card>
            </div>

            <div className="lg:col-span-5 space-y-5">
              <Card title="Captured number"><DigitStrip entity={state?.entity ?? null} risk={state?.risk} unchecked={state ? !state.ripcord_enabled : false} truth={scenario?.source === "recorded" ? scenario.truth : null} /></Card>
              <Card title="Ripcord's decision"><RiskPanel risk={state?.risk ?? null} ripcordEnabled={ripcordEnabled} /></Card>
              <Card title="Resolved this call"><SessionHistoryPanel current={state?.history ?? []} /></Card>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
