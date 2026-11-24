# Ripcord

**A safety layer for voice agents: it catches a misheard number before the agent acts on it.**

A voice agent hears "one five eight zero" and writes down "150". Nothing crashes. The call sounds normal. The wrong order gets looked up. Ripcord sits around the agent, gives every critical number a risk score, and if the risk is high it stops and asks the caller one short question first.

```
caller speaks  ->  speech-to-text (words + confidence)  ->  Ripcord scores the risk
                                                              |
                                        low risk  ->  act
                                        high risk ->  ask one question  ->  verified  ->  act
```

The action layer (`workflow_guard.py`) refuses to run on a number that is not `VERIFIED`, or that is not a valid 4-digit number. That is an exception in code (`UnverifiedEntityError`), not a UI rule.

## What is in version 2

- **A learned risk model** (`backend/app/risk_model.json`). A small logistic regression over 12 features you can read: word confidence, digit count, how the number was said, speaking speed, confusable sounds (fifteen / fifty), repeats, corrections. Every decision comes with its reasons.
- **A real benchmark.** 900 calls made from 109 synthetic voices with noise, phone-line, echo and fast-speech effects, run through a real streaming speech recogniser that gives genuine per-word confidence. Train / validation / test never share a voice or an order number.
- **A dashboard with four tabs.** Live demo, Side by side (plain agent vs Ripcord on the same audio), Benchmark (every number with 95% intervals), Playground (type a sentence, drag the confidence, watch the decision change).
- **Better conversation logic.** If the caller repeats the number, it is scored again. After 3 tries it hands off to a human. If the caller corrects a number that was already accepted, it un-verifies it, flags the earlier action and checks the new number.
- **116 tests**, all passing (a few skip themselves if the benchmark data is not present).

## The results, in simple words

Test split: 297 calls the model never saw. 95% intervals are in `docs/evaluation.md`.

| | Acts on a wrong number | Resolved correctly | Needless questions |
|---|---|---|---|
| Plain agent (no check) | **46.1%** | 51.8% | 0% |
| Always read back | 0% | 34.0% | 100% |
| ASR-confidence threshold | 3.4% | 59.9% | 0% |
| Weakest-digit threshold | 3.0% | 57.9% | 7.8% |
| Ripcord v1 (hand-tuned rules) | 2.4% | 52.9% | 22.1% |
| **Ripcord v2 (learned)** | **2.7%** | 56.9% | 7.8% |

What this says, honestly:

1. **The check matters a lot.** The recogniser got about 47% of the numbers wrong (mostly dropped or garbled digits). A plain agent acts on a wrong number almost half the time. With Ripcord it is under 3%.
2. **v2 asks about one third as many needless questions as v1** (7.8% vs 22.1%) for the same safety.
3. **Simple baselines are almost as safe.** A plain "ask if the confidence is low" rule is within the margin of error of v2 on wrong actions (the intervals overlap). v2 is not magic. What it adds is reasons for every decision, a calibrated probability (calibration error 0.0098), and better handling of the hard case below.
4. **The hard case is still hard.** Some wrong numbers look perfectly normal: 4 digits, high confidence. Only 7 such calls are in the test set and v2 caught none of them at its operating point, so the test set cannot say anything about this. On the larger cross-validated sample (528 well-formed captures from train + validation) v2 ranks them at AUROC **0.80**, while the recogniser's own confidence scores about **0.47**, which is a coin flip. That is the real contribution, but it needs more data to be proven.
5. **About 40% of calls end "unresolved"** because the benchmark replays only one caller reply. In a live call the caller can answer again.

## Run it

You need Python 3.11+ and Node 20+ (tested on Python 3.13, Node 22).

```bash
# backend
python3 -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env                                    # MOCK_MODE=true works with no API key
cd backend && uvicorn app.main:app --port 8000
```

**Option 1: one service.** Build the dashboard once and FastAPI serves it:

```bash
cd frontend && npm install && npm run build
# open http://localhost:8000
```

**Option 2: dev mode with hot reload.**

```bash
cd frontend && npm install && npm run dev               # open http://localhost:5173
```

The demos replay recorded clips (real recogniser output from the validation split), so you do not need a key to see the full story. For a live microphone, set `ASSEMBLYAI_API_KEY` and `MOCK_MODE=false`.

### Tests

```bash
cd backend && python -m pytest -q
```

### Re-run the benchmark

See [`benchmark/README.md`](benchmark/README.md). It needs about 400 MB of open-source models and roughly 30 minutes on two CPU cores. The dashboard and backend do not need any of it; they only read the two files it produces.

## How it works

| File | Job |
|---|---|
| `entity_detector.py` | Finds the order number in the words and keeps each digit's confidence |
| `risk_engine.py` + `risk_model.py` | Turns the capture into a probability that it is wrong, with reasons |
| `clarification_engine.py` | Writes one targeted question ("was it one-five-eight-zero?") |
| `session.py` | Runs the conversation: ask, re-score, verify, escalate, handle corrections |
| `workflow_guard.py` | The gate. No verified, valid number means no action |
| `benchmark.py` | Replays recorded calls through any policy and scores them |
| `assemblyai_service.py` | Live AssemblyAI v3 streaming client |

More detail: [`docs/architecture.md`](docs/architecture.md). The full benchmark report with failures and training notes: [`docs/evaluation.md`](docs/evaluation.md). A short live-demo script: [`docs/demo-script.md`](docs/demo-script.md). Deploying: [`docs/deployment.md`](docs/deployment.md).

## Limits (please read)

- **The voices are synthetic and the recogniser is open-source, not AssemblyAI.** Confidence scores from different engines are not interchangeable. Before quoting any number as real-world accuracy, retrain on your own recogniser's output. `benchmark/import_transcripts.py` converts AssemblyAI-style transcript JSON for that, but it is tested on fixtures only, not on the live API.
- **One entity type** (a 4-digit order number) in one simulated workflow. It is not a general voice-error detector.
- **The test set was scored after the model was fixed, and once more after a bug fix.** The bug: a wrong-length number could be "confirmed" by a garbled repeat. The fix and both runs are disclosed in `docs/evaluation.md`.
- **Valid-looking wrong numbers** are rare in this data (7 in the test set), so the hard-case result rests on cross-validation, not the held-out test.
- The dashboard and the benchmark were built to be honest, so some numbers look unimpressive. They are the real ones.

## Next steps

- Retrain and re-test on real human voices through the production recogniser.
- Collect more valid-looking wrong captures, since that is where the model matters most.
- More entity types (booking codes, phone numbers) using the same detect / score / ask / guard pattern.
- Let the cost ratio (wrong action vs one question) be set per workflow. It is one flag in `train_risk_model.py`.

## About the older hackathon files

`docs/submission.md`, `docs/video-script.md` and `submission/` (pitch deck and scripts) describe the **original hackathon version (v1)**: hand-tuned rules, 10 authored scenarios. They were not rewritten for v2, so their numbers and claims are out of date. This README and `docs/evaluation.md` are the current ones.

## License

MIT, see [`LICENSE`](LICENSE).
