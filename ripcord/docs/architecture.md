# Architecture

## AssemblyAI API surface actually used

Verified against the live AssemblyAI documentation on 2026-09-19 (docs.assemblyai.com — real-time / "Universal-Streaming" section). This is the exact, current v3 Streaming WebSocket API, not a guessed or legacy shape.

| Concern | Mechanism used | Where |
|---|---|---|
| Connect | `wss://streaming.assemblyai.com/v3/ws?sample_rate=16000&encoding=pcm_s16le&speech_model=universal-streaming-english` | `assemblyai_service.py` |
| Auth (server-side) | `Authorization` header with the raw API key | `assemblyai_service.py` |
| Auth (browser-side, if ever needed) | Short-lived token from `GET /v3/token?expires_in_seconds=N` | `generate_temporary_token()` |
| Session lifecycle | First server message is `Begin`; client can send `Terminate` to end cleanly | `AssemblyAIStreamingSession` |
| Live transcript + word confidence | `Turn` message: `transcript`, `end_of_turn`, `words[].confidence` | `entity_detector.py` consumes this directly |
| Vocabulary boosting | `keyterms_prompt` query param, seeded with this workflow's vocabulary ("order number", "booking reference", ...) | `StreamingConfig.keyterms_prompt` |
| Feeding agent context back in | `UpdateConfiguration` message with `agent_context` | `update_agent_context()` |
| Forcing a turn boundary | `ForceEndpoint` message | `force_endpoint()` |

Ripcord's browser client never talks to AssemblyAI directly. Audio flows: **mic → browser WebSocket → Ripcord backend → AssemblyAI WebSocket**, and Turn messages flow back the same path in reverse, through the risk pipeline, before the frontend ever sees them. This keeps the permanent API key server-side and gives Ripcord a single place to run the risk engine regardless of client.

If a future AssemblyAI docs update changes any of the above (field names, message types), update this table and `assemblyai_service.py` together — don't let the two drift.

## Connection resilience

Two independent links can drop, and each is handled at the layer that owns it:

- **Backend ↔ AssemblyAI.** If the streaming WebSocket drops mid-call (network blip, idle timeout), `main.py`'s `read_real_transcripts()` retries the connection with capped exponential backoff (`AAI_RECONNECT_BASE_DELAY_S * 2^attempt`, up to `MAX_AAI_RECONNECT_ATTEMPTS`). `SessionState.connection_status` tracks `connecting → live → reconnecting → disconnected` so the dashboard reflects reality instead of silently going stale.
- **Browser ↔ backend.** `frontend/src/hooks/useRipcordSession.ts` reconnects its own WebSocket with the same backoff pattern if the browser link drops, up to a 10s cap, and resumes rendering state as soon as it's back.

Neither retry loop hides failure indefinitely — after the retry budget is exhausted, the frontend gets an explicit error, never a silently frozen UI.

## Decision latency

`SessionOrchestrator.process_turn()` times itself (wall-clock, per turn) and exposes the result as `SessionState.last_decision_latency_ms`, shown as a badge in the dashboard header. This is the time from receiving a finalized Turn to Ripcord's verify/clarify decision — it does not include AssemblyAI's own transcription latency, which is a separate, externally-measured quantity.

## Session history

Two distinct layers, deliberately kept simple:

- **In-session** (`SessionState.history`, a list of `ResolvedEntry`): every entity that reaches a terminal state (`VERIFIED`) this session, whether via auto-verification or after clarification. Drives the dashboard's Session History panel.
- **Cross-session** (`backend/app/event_log.py`): a local JSONL append-log (`backend/data/sessions.jsonl`) written when a WebSocket session ends. No database dependency — Supabase remains a documented upgrade path (see spec section 10) if a team wants multi-instance/durable storage, but the project runs standalone without it.

## Data flow, end to end

```
Browser mic
   -> useMicCapture (PCM16 @16kHz)
   -> WebSocket /ws/session (binary frames)
   -> main.py forwards to AssemblyAIStreamingSession
   -> AssemblyAI v3 streaming websocket
   -> Turn message back
   -> SessionOrchestrator.process_turn()
        -> entity_detector.detect_critical_entity()
        -> risk_engine.assess_risk()          [Mode B only: learned model + conversation rules]
        -> clarification_engine.build_clarification()  [if should_clarify]
        -> workflow_guard.execute_order_lookup()  [only if VERIFIED]
   -> SessionState broadcast back over /ws/session
   -> React dashboard renders it
```

Mock mode replaces only the first three steps (mic + AssemblyAI) with `mock_service.stream_scenario()`, which replays recorded clips (`demo/recorded_scenarios.json`, real recogniser output) and the 10 hand-written scripts (`demo/scenarios.json`) as identically-shaped `Turn` dicts. Every step from `SessionOrchestrator.process_turn()` onward is the same code path in both modes — the before/after demo is not staged.

## Safety rule, enforced in code

`workflow_guard.execute_order_lookup()` raises `UnverifiedEntityError` if called with anything other than `EntityStatus.VERIFIED`. `SessionOrchestrator` is the only caller, and it only calls it after either (a) the risk engine found the capture safe enough to skip clarification, or (b) the user has explicitly confirmed or corrected the value in response to a clarification question. There is no code path that marks an entity `VERIFIED` without one of those two things happening.

Mode A (Ripcord OFF) deliberately does **not** go through `workflow_guard` — it calls a separate `naive_agent_accept()` function that mimics a normal agent with no reliability layer, specifically so the before/after demo has a real contrast to show.

## The risk engine (v2: learned, still explainable)

`risk_engine.py` has two layers. Neither is an LLM, and both can explain themselves.

**1. Evidence model** (`risk_model.py`, weights in `risk_model.json`). A small logistic regression estimates the probability that the captured number is *wrong*, from how it was heard:

| Feature | Meaning |
|---|---|
| `tok_min`, `tok_mean`, `low_frac` | weakest number-word confidence, average, share of shaky words |
| `context_conf` | confidence of the words around the number |
| `len_dev` | digit count is not 4 |
| `pairs`, `cardinal`, `teen_ten` | spoken style: "fifteen eighty", "one thousand five hundred…", fifteen/fifty-type words |
| `homophones` | a digit heard as an everyday word ("won", "to", "for", "ate") |
| `no_carrier`, `competing` | no "order number" phrase; more than one number in the turn |
| `rate` | speaking speed (only when real word timings exist) |

The dashboard shows each feature's push on the log-odds *relative to a typical correctly-heard capture*, so a switched-off flag shows nothing and a weak digit shows up as a big red bar. The training script saves that reference (`ref`) in the model file.

**2. Conversation rules.** The caller's own words are direct evidence, not a statistical guess: contradicting an earlier number, repeating it unprompted, or saying "no, that's wrong" each force a question on their own. A restated number inside a clarification is *not* treated as a contradiction.

**Threshold.** The model's output is compared with a threshold chosen by cross-validation under a cost model (acting on a wrong number costs 10× a question; change it with `--cost-ratio`). Override it with `RISK_CLARIFY_THRESHOLD`.

**Fallback.** If `risk_model.json` is missing, the engine falls back to the original v1 hand-weighted rules (`assess_risk_rules`), so the project always runs. v1 is also kept as a baseline in the benchmark.

`end_of_turn_confidence` from AssemblyAI is blended into the mean-confidence feature (0.7 word / 0.3 turn) when it is present. Recorded or scripted replays do not carry it, so it is left out rather than invented.

## What happens after a question

`session.py` runs a small state machine (see its docstring):

- **"Yes"** (heard with real confidence) → verified, workflow resumes.
- **A restated number** ("no, it's 1580") → treated as a *new* capture from the same noisy recogniser: scored again; if still shaky it is read back ("I heard 1-5-8-0, is that right?"), otherwise accepted.
- **A plain "no"** or an unclear answer → ask for the digits one at a time. An unclear answer never counts as a yes.
- **Three failed rounds** → escalate to a human. Ripcord never guesses.
- **A correction of a number it already accepted** ("no, I said 3719") → the old number stops counting as verified, the earlier action is flagged for review, and the new number is checked with the contradiction on record. This is the second chance for a confident-but-wrong first capture.

## Spoken-number parsing

`entity_detector.py` turns the transcript into a candidate number and tracks which word each digit came from, so confidence is per digit:

1. Already digitized by the recogniser's text normalisation (`"1580"`, or `"15 80"`).
2. Digit by digit, with `oh`/`zero`, and `double`/`triple` shorthand.
3. In pairs ("fifteen eighty", "seventy seven forty four").
4. As one cardinal ("one thousand five hundred eighty", "fifteen hundred eighty").
5. Homophones recovered from common mis-transcriptions: `won`→1, `to/too`→2, `for/fore`→4, `ate`→8.

It also records the style, the carrier phrase, teen/ten words, competing numbers and speaking rate, which feed the evidence model. `classify_reply()` reads the caller's answer to a yes/no question (whole words only, so "know" is not "no").

## The benchmark and the dashboard

`benchmark/` builds real recogniser output (synthetic voices → noise/phone/echo → a streaming recogniser with genuine per-word probabilities), trains the evidence model on the train+validation splits, and scores every system once on a held-out test split. `docs/evaluation.md` is generated from the results; the dashboard's **Benchmark** tab reads `benchmark/results/benchmark_results.json` through `GET /api/benchmark`. The **Playground** tab calls `POST /api/assess` with any transcript and per-word confidences.

## Optional LLM usage

`clarification_engine.rephrase_with_llm()` is a no-op hook for optionally making the clarification question sound more natural via an LLM call. It is never used to decide *whether* to clarify — that decision is 100% deterministic, in `risk_engine.py`, so it can be explained to a judge in one sentence per signal.

## Deployment

- **Frontend**: Vercel. `frontend/` is a standard Vite build (`npm run build` → `dist/`).
- **Backend**: needs a persistent process for WebSockets, which Vercel's serverless functions don't support well for long-lived connections — deploy to Render, Railway, or Fly.io instead. Point the frontend's `/api` and `/ws` proxy (or a `VITE_BACKEND_URL` env var, if you add one) at that host.
- **Required env vars on the backend host**: `ASSEMBLYAI_API_KEY`, `MOCK_MODE=false`, `CORS_ORIGINS=https://<your-vercel-domain>`.
- **CORS**: the backend's `CORSMiddleware` reads `CORS_ORIGINS` from the environment — add your deployed frontend origin there, comma-separated if there's more than one (e.g. a Vercel preview URL plus the production domain).
