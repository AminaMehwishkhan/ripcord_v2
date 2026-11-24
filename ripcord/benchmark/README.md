# Ripcord benchmark

Everything here is **dev-time only**. The Ripcord backend and dashboard do not need it; they only read the two files it produces:

- `backend/app/risk_model.json` — the trained evidence model
- `benchmark/results/benchmark_results.json` — the scores shown on the dashboard's **Benchmark** tab

## What it does

```
build_dataset.py   text-to-speech voices -> noise / phone / echo / fast speech -> a real streaming recogniser
                   -> data/*.jsonl  (transcript + REAL per-word probability + the true number, plus the
                                     caller's recorded "yes" and "no, it's ..." replies)
train_risk_model.py  fits the logistic regression on the train + val splits only (5-fold CV picks the
                   regularisation and the question threshold)
evaluate.py        scores six systems on the held-out test split (after the model is fixed) -> results/benchmark_results.json
make_report.py     regenerates docs/evaluation.md from that results file
make_demo_scenarios.py  picks real clips from the validation split for the dashboard demos
```

The splits are made by **speaker and by number**, so nothing in `test` shares a voice or an order number with the training data. The six systems are: no check, always read back, an ASR-confidence threshold, a weakest-digit threshold, Ripcord v1 (hand-tuned rules) and Ripcord v2 (learned). The threshold baselines are tuned with the same cost model and the same data as v2, so the comparison is fair.

## Rebuild it

```bash
pip install -r benchmark/requirements.txt          # numpy, scipy, sherpa-onnx
# models (about 400 MB) from https://github.com/k2-fsa/sherpa-onnx/releases :
#   asr-models: sherpa-onnx-streaming-zipformer-en-2023-06-26
#   tts-models: vits-vctk
export RIPCORD_MODELS=/path/to/models               # folder that contains both

cd benchmark
python build_dataset.py --n 900 --shard 0 --nshards 2 &   # two workers; ~30 minutes on 2 CPU cores
python build_dataset.py --n 900 --shard 1 --nshards 2
python train_risk_model.py [--cost-ratio 10]
python evaluate.py
python make_report.py
python make_demo_scenarios.py
```

`--cost-ratio` says how much worse it is to act on a wrong number than to ask one question. Raise it for higher-stakes workflows (payments, medication) and the threshold drops, so Ripcord asks more often.

## Use your own recogniser (recommended before quoting numbers)

The numbers in `docs/evaluation.md` come from an open-source recogniser on synthetic voices. They show that the method works, but a different recogniser has different confidence scores, so the weights and the threshold should be re-fitted on *its* output.

Each line of `data/*.jsonl` is one call. The only things Ripcord needs are:

```json
{"id": "r0001", "split": "train", "speaker": 12, "true_value": "1580", "condition": "clean",
 "asr":       {"transcript": "my order number is one five eight zero",
               "words": [{"text": "my", "confidence": 0.98, "start": 320, "end": 480}, "..."]},
 "reply_yes": {"transcript": "yes that's right", "words": ["..."]},
 "reply_no":  {"transcript": "no it's one five eight zero", "words": ["..."]}}
```

`reply_no` is optional. Word `confidence` is a probability from 0 to 1, `start`/`end` are in milliseconds (use 0 if you do not have them; speaking rate is then ignored). Keep `speaker` and `true_value` disjoint between `train`, `val` and `test`. Drop your lines into `benchmark/data/` (and remove the generated ones), then run `train_risk_model.py`, `evaluate.py` and `make_report.py`. Nothing else changes.

`import_transcripts.py` converts AssemblyAI-style transcript JSON (a `words` list with `text`, `start`, `end`, `confidence`) into those lines — see its docstring. It is tested against fixtures only, not against the live API.

## Honest limits

- The speech is synthetic and the recogniser is a small open-source model that gets many spoken numbers wrong (mostly dropped or garbled digits). Errors that still *look* like a normal 4-digit number are rarer; they are reported separately for that reason.
- One entity type, one workflow.
- The 5-fold CV picks lambda and the threshold on training data. The test split is only read by `evaluate.py`.
