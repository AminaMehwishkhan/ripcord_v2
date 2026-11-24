import { useEffect, useRef } from "react";
import type { ConversationTurn } from "../types";
import { pct } from "../lib/format";

function Words({ turn }: { turn: ConversationTurn }) {
  if (turn.words.length === 0) return <>{turn.text}</>;
  return (
    <>
      {turn.words.map((w, i) => {
        const tone = w.confidence >= 0.85 ? "" : w.confidence >= 0.65 ? "w-mid" : "w-low";
        const isNum = /^(\d+|zero|oh|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|double|triple)$/i.test(
          w.text.replace(/[^\w]/g, ""),
        );
        return (
          <span key={i}>
            <span className={`w ${tone} ${isNum ? "w-num" : ""}`} title={`${pct(w.confidence)} confident`}>
              {w.text}
            </span>{" "}
          </span>
        );
      })}
    </>
  );
}

export function ConversationView({ turns, empty, maxHeight = 360 }: {
  turns: ConversationTurn[]; empty?: string; maxHeight?: number;
}) {
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [turns.length]);

  if (turns.length === 0) {
    return <p className="text-dim text-sm py-6 text-center">{empty ?? "The conversation will appear here."}</p>;
  }
  return (
    <div className="flex flex-col gap-2.5 overflow-y-auto pr-1" style={{ maxHeight }} role="log" aria-live="polite">
      {turns.map((t, i) => (
        <div key={i} className={`rc-fade-in flex flex-col ${t.role === "agent" ? "items-end" : t.role === "system" ? "items-center" : "items-start"}`}>
          <span className="text-[10.5px] uppercase tracking-wider text-faint mb-0.5 px-1">
            {t.role === "caller" ? "Caller (as heard)" : t.role === "agent" ? "Voice agent" : "System"}
            {t.note ? ` · ${t.note}` : ""}
          </span>
          <div className={`bubble bubble-${t.role}`}>
            {t.role === "caller" ? <Words turn={t} /> : t.text}
          </div>
        </div>
      ))}
      <div ref={end} />
      <p className="text-[11px] text-faint">Underlined words are ones the recogniser itself was unsure about.</p>
    </div>
  );
}
