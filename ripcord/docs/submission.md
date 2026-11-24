# lablab.ai Submission — Copy/Paste Fields

> **Note:** this file describes the original hackathon version (v1: hand-tuned rules, 10 authored scenarios). It was not rewritten for v2, so numbers like "22 tests" and "1/10 → 0/10" are out of date. Current results: [`docs/evaluation.md`](evaluation.md) and the top-level README.

Everything below is written to drop directly into the lablab.ai submission form for the **AssemblyAI - Voice Agent Hackathon** (Sep 1–30, 2026). Fill in the `[bracketed]` placeholders before submitting — those are the only parts specific to you.

---

## Project title

```
Ripcord — Real-Time Self-Repair for Voice Agents
```

## Short description (≤150 chars, adjust to the form's exact limit)

```
Ripcord pauses a voice agent before it acts on a misheard number, asks one targeted question, and verifies before executing.
```

## Long description

```
Voice agents don't usually fail by crashing — they fail by sounding confident while quietly acting on the wrong number. "One-five-eight-zero" becomes "one-five-zero," the wrong order gets looked up, and nothing about the conversation ever signaled a problem.

Ripcord is a reliability layer that sits around a voice agent and treats every critical numeric entity (an order number, booking reference, confirmation code) as unverified until proven otherwise. It scores each capture on explainable signals pulled directly from AssemblyAI's real-time Streaming v3 API — per-word confidence, end-of-turn confidence, repetition, contradiction, and correction language — and when the risk crosses a threshold, it pauses the workflow and asks one targeted clarifying question instead of guessing.

The safety rule is enforced in code, not convention: the action layer physically refuses to execute on an entity that isn't marked VERIFIED (an UnverifiedEntityError, not a UI nicety).

What's built:
- Full backend pipeline (FastAPI + WebSockets): entity detection, a deterministic multi-signal risk engine, targeted clarification generation, and the workflow guard, all backed by AssemblyAI's real v3 streaming API (word + end-of-turn confidence, keyterms_prompt, agent_context)
- A React/Vite/Tailwind dashboard showing the live transcript, risk gauge, clarification flow, event timeline, session history, and a live mic waveform
- A side-by-side before/after demo — the same real pipeline run with Ripcord off vs on
- An evaluation harness that computes real metrics from 10 hand-authored scenarios every time it runs (not hand-typed numbers): entity errors dropped from 1/10 to 0/10 with Ripcord on
- 25 passing automated tests
- Auto-reconnect with backoff on both the AssemblyAI link and the browser WebSocket link, so a dropped connection mid-call doesn't kill the session

Built solo for the AssemblyAI Voice Agent Hackathon 2026.
```

## Tags / Technologies

```
AssemblyAI, Voice AI, Speech-to-Text, Python, FastAPI, WebSockets, React, TypeScript, Vite, Tailwind CSS
```

## Category

```
Voice Agents / Developer Tools / Reliability & Safety
```

## Cover image

16:9, PNG or JPG. Suggested: a screenshot of the dashboard mid-clarification (the amber "WORKFLOW PAUSED" panel is the single most legible frame for a thumbnail — it reads instantly even shrunk down).

## Demo application platform

```
[Render / Railway / Fly.io for the backend] + [Vercel for the frontend] — see docs/deployment.md
```

## Demo application URL

```
[your deployed frontend URL]
```

## Public GitHub repository

```
[your GitHub repo URL] — MIT licensed (see LICENSE)
```

## Video presentation

MP4, ≤5 minutes. Script: `docs/video-script.md`. Structure follows lablab's own judging rubric so nothing scored gets left out: problem → solution/demo → business case & market → competitive differentiation → roadmap.

## Slide deck

PDF: `submission/ripcord-pitch-deck.pdf` (source: `submission/ripcord-pitch-deck.pptx`). 9 slides — title, problem, solution, why AssemblyAI, architecture, real evaluation results, business value, roadmap, close.

---

## Pre-submit checklist

- [ ] Filled in `[Your Name]` in `LICENSE`, the deck's title slide, and the deck's close slide
- [ ] Filled in GitHub URL, live demo URL, and contact email on the deck's close slide (`submission/ripcord-pitch-deck.pptx` → regenerate the PDF after editing, see `submission/README.md`)
- [ ] Backend deployed with `MOCK_MODE=false` and a real `ASSEMBLYAI_API_KEY`, OR deployed with `MOCK_MODE=true` if you're demoing only the mock scenarios (say so explicitly in the video — don't let a judge think mock mode is the real pipeline)
- [ ] `CORS_ORIGINS` on the deployed backend includes the deployed frontend's exact origin
- [ ] Repo is public, contains `LICENSE`, and has no committed `.env` or API keys (`.gitignore` already excludes `.env`, `.venv`, `node_modules`, `dist` — double-check before pushing)
- [ ] Video is under 5 minutes and actually shows the before/after (Mode A vs Mode B) — this is the single highest-leverage 15 seconds of the whole submission
- [ ] Recorded video and exported slides pulled from the *deployed* app, not localhost, so the demo URL and what's on screen match
