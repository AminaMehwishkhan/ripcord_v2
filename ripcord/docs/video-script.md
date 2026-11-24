# Submission Video Script (target: 4:30–5:00)

> **Note:** this file describes the original hackathon version (v1: hand-tuned rules, 10 authored scenarios). It was not rewritten for v2, so numbers like "22 tests" and "1/10 → 0/10" are out of date. Current results: [`docs/evaluation.md`](evaluation.md) and the top-level README.

lablab.ai scores video+slides on **Presentation** (problem/solution/value prop, market analysis, future goals — see `docs/submission.md`), and separately on **Application of Technology**, **Business Value**, and **Originality**. This script is ordered so all four get hit inside the 5-minute cap, not just the demo.

Record from the **deployed** app (not localhost) so the URL on screen matches what's in the submission form.

---

### 0:00–0:20 — Hook & problem (Presentation)
> "Voice agents don't usually fail by crashing. They fail by sounding completely normal — while quietly acting on the wrong number. 'One-five-eight-zero' becomes 'one-five-zero.' Nothing in the conversation tells you that happened."

Show: title slide, then straight to the app.

### 0:20–0:45 — Solution in one breath
> "Ripcord is a reliability layer for voice agents. It treats every critical number as unverified until proven otherwise, scores it on explainable signals, and pauses to ask before it acts."

Show: the solution flow diagram slide (Critical entity → Risk engine → Verified/Uncertain → Execute/Clarify).

### 0:45–2:15 — Live demo: the before/after (Presentation + Originality)
- Toggle **Ripcord OFF**, run scenario 2 ("1580 heard as 150"). Point at the Entity Detector: `150`, no pause, action fires on the wrong number.
- Toggle **Ripcord ON**, run the same scenario. Point at the Risk Signals card filling in, the amber "WORKFLOW PAUSED" panel, and read the clarification question aloud.
- Click **Yes, correct** (or type the number). Point at the green ACTION card: `Order 1580 located safely.`

> "Same audio, same misheard capture. Without Ripcord, it silently proceeds. With Ripcord, it catches itself — one clarifying question, then the right action."

### 2:15–3:00 — Why AssemblyAI (Application of Technology)
> "This isn't a transcription wrapper. The risk score is built directly on AssemblyAI's real-time Streaming v3 signals — per-word confidence, end-of-turn confidence blended in, keyterms_prompt boosting this workflow's exact vocabulary, and agent_context feeding the agent's own question back in to improve accuracy on short replies."

Show: the "Built on AssemblyAI's real-time signals" slide.

### 3:00–3:20 — Proof, not slideware
> "And these aren't invented numbers — this evaluation panel runs the real pipeline against 10 scripted scenarios every time you load it. One in ten entity errors without Ripcord, zero with it, on this test set."

Show: Evaluation tab or the results slide with the bar chart.

### 3:20–4:10 — Business value (Business Value criterion)
> "The target user is any team shipping voice agents into transactional flows — order support, logistics dispatch, appointment booking, fintech onboarding — where a misheard number has a real, costly downstream effect. Most voice-agent tooling today competes on latency and how natural the voice sounds. Almost none of it competes on correctness under uncertainty — that's a distinct, underserved axis as voice agents move into higher-stakes work. This could ship as usage-based middleware priced per verified transaction, or as a per-seat license for teams embedding the guard layer directly into their own agent stack."

Show: the business value slide (Target user / Market angle / Revenue model).

### 4:10–4:40 — Roadmap & close
> "Right now this protects one entity type end to end, on purpose — the same detector, risk engine, clarify, and guard pattern extends to phone numbers, confirmation codes, and beyond without changing the architecture. Ripcord turns voice uncertainty into a controlled verification step — before the mistake becomes an action."

Show: roadmap slide, then close slide with GitHub / demo / contact links on screen for a beat.

### 4:40–5:00 — Buffer
Leave this as slack — trim from the demo section (0:45–2:15) first if you're running long; it's the most forgiving part to tighten since the audience is watching, not listening to narration.

---

**Recording tips:**
- Do one full dry run with a stopwatch before recording for real — the "how to win" guidance from lablab is explicit that judges reward a clean 4-minute cut over a padded 5-minute one.
- Caption or verbally flag mock-mode segments if `MOCK_MODE=true` on your deployment — don't let a judge mistake replayed scenarios for a live mic demo.
- Keep captions/text on slides large enough to read at 720p — assume some judges watch on mobile.
