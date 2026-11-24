import { useState } from "react";
import { Mic } from "lucide-react";
import type { ClarificationQuestion, Scenario } from "../types";

/** What the caller says back. Recorded replies are real recogniser output from the benchmark. */
export function ReplyPanel({ clarification, scenario, onRecorded, onType, escalated }: {
  clarification: ClarificationQuestion | null;
  scenario: Scenario | undefined;
  onRecorded: (kind: "yes" | "no") => void;
  onType: (text: string) => void;
  escalated: boolean;
}) {
  const [text, setText] = useState("");

  if (escalated) {
    return (
      <div className="rounded-xl border border-[var(--rc-red)]/40 bg-rose-400/5 p-4 rc-fade-in">
        <p className="font-semibold text-rose-300">Handed off to a human</p>
        <p className="text-sm text-dim mt-1">
          Three questions did not settle the number, so Ripcord refuses to guess. In production this is where the call
          transfers or the caller types the number on the keypad.
        </p>
      </div>
    );
  }
  if (!clarification) return null;

  const recorded = scenario?.has_replies;
  const yes = () => (recorded ? onRecorded("yes") : onType("Yes, that's right."));
  const no = () => (scenario?.has_replies && scenario.truth && clarification.candidate_value !== scenario.truth ? onRecorded("no") : onType("No, that's wrong."));
  const askingDigits = clarification.kind === "repeat_digit_by_digit";

  return (
    <div className="rounded-xl border border-[var(--rc-amber)]/40 bg-amber-400/5 p-4 rc-fade-in">
      <div className="flex items-center gap-2 mb-2">
        <span className="rc-pulse text-amber-300">⏸</span>
        <span className="text-xs font-bold tracking-wider text-amber-300">WORKFLOW PAUSED — WAITING FOR THE CALLER</span>
      </div>
      <p className="text-[17px] leading-snug mb-3">“{clarification.question}”</p>
      <div className="flex flex-wrap gap-2 mb-3">
        {!askingDigits && (
          <>
            <button className="btn btn-good btn-sm" onClick={yes}>
              <Mic size={14} /> Caller says “yes”
            </button>
            <button className="btn btn-bad btn-sm" onClick={no}>
              <Mic size={14} /> Caller says “no”
            </button>
          </>
        )}
        {askingDigits && scenario?.has_replies && scenario.truth && (
          <button className="btn btn-sm" onClick={() => onRecorded("no")}>
            <Mic size={14} /> Caller says the number again
          </button>
        )}
      </div>
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (text.trim()) {
            onType(text.trim());
            setText("");
          }
        }}
      >
        <input className="field" value={text} onChange={(e) => setText(e.target.value)} placeholder="…or type what the caller says, e.g. “one five eight zero”" aria-label="Caller reply" />
        <button className="btn btn-sm" type="submit">Send</button>
      </form>
    </div>
  );
}
