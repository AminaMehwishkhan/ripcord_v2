"""
train_risk_model.py — fit Ripcord's evidence model on recorded recogniser output.

Only the `train` and `val` splits are used (5-fold cross-validation picks the
regularisation strength and the clarify threshold). The `test` split is never
read here — it is scored once, by evaluate.py.

Training examples are every utterance Ripcord would have to judge:
  * the first thing the caller says ("my order number is …"), and
  * the number restated in a "no, it's …" reply (no carrier phrase, short).
Label = 1 when the number the detector extracted is NOT the number spoken.

Why the model is fitted on well-formed captures only
  A capture that is not 4 digits long is wrong almost every time, and that is easy to see
  without any learning. Left in, it swamps the data (most of this recogniser's mistakes are
  dropped digits) and the model learns "length" instead of "how sure was the recogniser".
  The dangerous mistakes are wrong numbers that LOOK fine, so the model is fitted on those
  captures, and the wrong-length rate (`invalid_format_p`) is measured separately.

The weights are sign-constrained (more confidence never raises risk; every warning flag only raises it)
so the explanations shown in the dashboard can be trusted.

Because few well-formed captures are wrong, the weights are shrunk toward a sensible prior
(lower confidence = riskier) instead of toward zero. Cross-validation decides how strong
the shrinkage should be, and whether to use the prior at all.

Cost model for the threshold: accepting a wrong number costs R (default 10),
asking a question costs 1. Raise --cost-ratio for higher-stakes workflows.

    python train_risk_model.py [--cost-ratio 10]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.benchmark import auroc, entity_of, load_items, reply_entity_of  # noqa: E402
from app.models import Word  # noqa: E402
from app.risk_model import FEATURES, extract_features  # noqa: E402

MODEL_OUT = ROOT / "backend" / "app" / "risk_model.json"
LAMBDAS = [0.0003, 0.001, 0.003, 0.01, 0.03, 0.1, 0.3, 1.0, 3.0]
# Prior direction in standardised units: one std lower confidence = about 0.7 higher log-odds of an error.
PRIOR = {"tok_min": -0.7, "tok_mean": -0.7, "low_frac": 0.4, "context_conf": -0.2}
# Common-sense signs, enforced during fitting: more confidence can never raise the risk of an error,
# and every warning flag can only raise it. Without this, features that overlap (weakest word vs
# average vs share of weak words) can take opposite signs on a small sample and make the
# explanations ("this digit made it SAFER") misleading.
SIGN = {"tok_min": -1, "tok_mean": -1, "context_conf": -1, "low_frac": 1, "len_dev": 1, "pairs": 1,
        "cardinal": 1, "teen_ten": 1, "homophones": 1, "no_carrier": 1, "competing": 1, "rate": 1}


def build_examples(items: list[dict]) -> tuple[np.ndarray, np.ndarray, list[str]]:
    rows, ys, src = [], [], []
    for it in items:
        e = entity_of(it)
        if e is not None:
            rows.append(extract_features(e))
            ys.append(0 if e.value == it["true_value"] else 1)
            src.append(it["id"])
        r = reply_entity_of(it)
        if r is not None:
            rows.append(extract_features(r))
            ys.append(0 if r.value == it["true_value"] else 1)
            src.append(it["id"])
    X = np.array([[np.nan if f[n] is None else f[n] for n in FEATURES] for f in rows], dtype=float)
    return X, np.array(ys, dtype=float), src


def fit(X: np.ndarray, y: np.ndarray, lam: float, prior: np.ndarray | None = None, iters: int = 60) -> np.ndarray:
    """Ridge-penalised logistic regression, shrunk toward `prior` (zeros if None). Bias is not penalised."""
    n, d = X.shape
    Xb = np.hstack([X, np.ones((n, 1))])
    reg = np.full(d + 1, lam)
    reg[-1] = 0.0
    th0 = np.zeros(d + 1)
    if prior is not None:
        th0[:d] = prior
    th = th0.copy()
    for _ in range(iters):
        p = 1 / (1 + np.exp(-np.clip(Xb @ th, -30, 30)))
        g = Xb.T @ (p - y) / n + reg * (th - th0)
        H = (Xb.T * (p * (1 - p))) @ Xb / n + np.diag(reg) + 1e-8 * np.eye(d + 1)
        step = np.linalg.solve(H, g)
        th -= step
        if np.max(np.abs(step)) < 1e-9:
            break
    return th


def fit_signed(X: np.ndarray, y: np.ndarray, lam: float, prior: np.ndarray | None, signs: np.ndarray) -> np.ndarray:
    """fit(), then drop any feature whose weight came out with the wrong sign and refit without it."""
    d = X.shape[1]
    active = np.ones(d, dtype=bool)
    for _ in range(d + 1):
        th = fit(X[:, active], y, lam, prior[active] if prior is not None else None)
        w = np.zeros(d)
        w[active] = th[:-1]
        bad = active & (w * signs < 0)
        if not bad.any():
            break
        active &= ~bad
    return np.concatenate([w, [th[-1]]])


def predict(X: np.ndarray, th: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-np.clip(np.hstack([X, np.ones((len(X), 1))]) @ th, -30, 30)))


def logloss(p: np.ndarray, y: np.ndarray) -> float:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def standardise(X: np.ndarray, mean=None, std=None):
    if mean is None:
        mean = np.nanmean(X, axis=0)
        mean = np.where(np.isnan(mean), 0.0, mean)
        Xf = np.where(np.isnan(X), mean, X)
        std = Xf.std(axis=0)
        std = np.where(std < 1e-6, 1.0, std)
    Xf = np.where(np.isnan(X), mean, X)
    return (Xf - mean) / std, mean, std


def best_threshold(p: np.ndarray, y: np.ndarray, ratio: float) -> tuple[float, list[float]]:
    grid = np.round(np.arange(0.02, 0.96, 0.01), 2)
    costs = []
    for t in grid:
        flagged = p >= t
        costs.append(float(ratio * np.sum((y == 1) & ~flagged) + np.sum(flagged)) / len(y))
    sm = np.convolve(costs, np.ones(5) / 5, mode="same")
    i = int(np.argmin(sm[2:-2]) + 2)
    return float(grid[i]), costs


def roc_points(scores: np.ndarray, labels: np.ndarray, max_points: int = 60) -> list[dict]:
    """Catch rate (misheard flagged) vs false-alarm rate (correct flagged) as the score threshold sweeps."""
    pos, neg = labels.sum(), (1 - labels).sum()
    order = np.argsort(-scores, kind="stable")
    s_sorted, y_sorted = scores[order], labels[order]
    tp = np.cumsum(y_sorted)
    fp = np.cumsum(1 - y_sorted)
    last_of_tie = np.r_[s_sorted[1:] != s_sorted[:-1], True]
    xs = np.r_[0.0, fp[last_of_tie] / neg]
    ys = np.r_[0.0, tp[last_of_tie] / pos]
    idx = np.unique(np.linspace(0, len(xs) - 1, min(max_points, len(xs))).astype(int))
    return [{"false_alarm": round(float(xs[i]), 4), "catch": round(float(ys[i]), 4)} for i in idx]


def best_1d_threshold(conf: np.ndarray, y: np.ndarray, ratio: float) -> float:
    """Flag when confidence < t. Same cost model as above."""
    grid = np.round(np.arange(0.2, 1.001, 0.01), 2)
    costs = [(ratio * np.sum((y == 1) & ~(conf < t)) + np.sum(conf < t)) / len(y) for t in grid]
    sm = np.convolve(costs, np.ones(5) / 5, mode="same")
    return float(grid[int(np.argmin(sm[2:-2]) + 2)])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cost-ratio", type=float, default=10.0)
    ap.add_argument("--folds", type=int, default=5)
    args = ap.parse_args()

    items = [i for i in load_items() if i["split"] in ("train", "val")]
    X_all, y_all, src_all = build_examples(items)
    j_len = FEATURES.index("len_dev")
    valid = X_all[:, j_len] == 0                      # a well-formed 4-digit capture
    p_invalid = float((y_all[~valid].sum() + 1) / ((~valid).sum() + 2))     # smoothed
    X, y, src = X_all[valid], y_all[valid], [s for s, v in zip(src_all, valid) if v]
    print(f"{len(items)} utterances (train+val) -> {len(y_all)} examples")
    print(f"  wrong-length captures: {int((~valid).sum())}, wrong {p_invalid:.1%} of the time (smoothed)")
    print(f"  well-formed captures (model is fitted on these): {len(y)}, misheard {int(y.sum())} ({y.mean():.1%})")

    # fold assignment by utterance id, so an utterance and its reply stay together
    ids = sorted(set(src))
    rng = np.random.default_rng(3)
    rng.shuffle(ids)
    fold_of = {i: k % args.folds for k, i in enumerate(ids)}
    folds = np.array([fold_of[s] for s in src])

    prior_vec = np.array([PRIOR.get(n, 0.0) for n in FEATURES])
    sign_vec = np.array([SIGN[n] for n in FEATURES], dtype=float)
    results = {}
    for use_prior in (False, True):
        for lam in LAMBDAS:
            oof = np.zeros(len(y))
            for k in range(args.folds):
                tr, te = folds != k, folds == k
                Ztr, m, sd = standardise(X[tr])
                Zte, _, _ = standardise(X[te], m, sd)
                keep = Ztr.std(axis=0) > 0
                th = fit_signed(Ztr * keep, y[tr], lam, prior_vec * keep if use_prior else None, sign_vec)
                oof[te] = predict(Zte * keep, th)
            results[(use_prior, lam)] = (logloss(oof, y), oof)
            print(f"  prior={'yes' if use_prior else 'no ':<3} lambda={lam:<6} CV log-loss {results[(use_prior, lam)][0]:.4f}"
                  f"  AUROC {auroc(list(oof), list(y.astype(int)))}")
    # One-standard-error rule: with only a few dozen misheard examples, prefer the most strongly
    # regularised setting whose CV log-loss is within one standard error of the best. That keeps the
    # model closer to the sensible prior (lower confidence = riskier) and less tied to this recogniser.
    def per_example_loss(oof_):
        pc = np.clip(oof_, 1e-6, 1 - 1e-6)
        return -(y * np.log(pc) + (1 - y) * np.log(1 - pc))
    best0 = min(results, key=lambda k: results[k][0])
    se = float(per_example_loss(results[best0][1]).std(ddof=1) / np.sqrt(len(y)))
    near = [k for k in results if results[k][0] <= results[best0][0] + se]
    best = max(near, key=lambda k: (k[1], k[0]))          # largest lambda; prefer the prior on ties
    print(f"best CV log-loss {results[best0][0]:.4f} (SE {se:.4f}); {len(near)} settings within one SE")
    use_prior, best_lam = best
    oof = results[best][1]
    thr, _ = best_threshold(oof, y, args.cost_ratio)
    thr = float(min(max(thr, 0.03), 0.9))
    print(f"chosen: prior={use_prior}, lambda={best_lam}, cross-validated threshold={thr}")

    Z, mean, std = standardise(X)
    keep = Z.std(axis=0) > 0      # a feature with no variance in the training data carries no information
    th = fit_signed(Z * keep, y, best_lam, prior_vec * keep if use_prior else None, sign_vec)
    w, b = th[:-1] * keep, float(th[-1])

    # baseline thresholds under the SAME cost model and the same well-formed captures
    ent_conf, ent_min, ent_y = [], [], []
    for it in items:
        e = entity_of(it)
        if e is not None and e.format_valid:
            ent_conf.append(e.confidence)
            ent_min.append(e.min_confidence)
            ent_y.append(0 if e.value == it["true_value"] else 1)
    ent_conf, ent_min, ent_y = map(np.array, (ent_conf, ent_min, ent_y))
    meta = {
        "trained": time.strftime("%Y-%m-%d"),
        "n_utterances": len(items),
        "n_examples": int(len(y_all)),
        "n_wellformed_examples": int(len(y)),
        "n_wellformed_misheard": int(y.sum()),
        "n_wrong_length_examples": int((~valid).sum()),
        "misheard_rate": round(float(y_all.mean()), 4),
        "wellformed_misheard_rate": round(float(y.mean()), 4),
        "lambda": best_lam,
        "shrunk_toward_prior": bool(use_prior),
        "cost_ratio": args.cost_ratio,
        "cv_logloss": round(results[best][0], 4),
        "cv_logloss_best_any": round(results[best0][0], 4),
        "selection_rule": "largest regularisation within one standard error of the best CV log-loss",
        "cv_auroc": auroc(list(oof), list(y.astype(int))),
        "baselines": {
            "asr_mean_conf_threshold": best_1d_threshold(ent_conf, ent_y, args.cost_ratio),
            "asr_min_conf_threshold": best_1d_threshold(ent_min, ent_y, args.cost_ratio),
        },
        "note": ("Trained on speech from an open-source recogniser (sherpa-onnx Zipformer) on synthetic "
                 "voices. Retrain on your own recogniser's output before trusting the absolute numbers."),
    }
    # The hard case, on the larger train+val sample: wrong numbers that already look like a normal
    # 4-digit number. Cross-validated predictions for the model; baselines have no fitted parameters.
    yi = y.astype(int)
    j_mean, j_min = FEATURES.index("tok_mean"), FEATURES.index("tok_min")
    hard_case = {
        "n": int(len(y)), "n_misheard": int(y.sum()),
        "auroc": {
            "ripcord_v2": auroc(list(oof), list(yi)),
            "asr_mean_conf": auroc(list(1 - X[:, j_mean]), list(yi)),
            "asr_min_conf": auroc(list(1 - X[:, j_min]), list(yi)),
        },
        "curves": {
            "ripcord_v2": roc_points(oof, y),
            "asr_mean_conf": roc_points(1 - X[:, j_mean], y),
            "asr_min_conf": roc_points(1 - X[:, j_min], y),
        },
    }
    meta["hard_case"] = hard_case
    print("hard-case AUROC (train+val, cross-validated for v2):", hard_case["auroc"])

    # reference capture for explanations: median of the correctly-heard examples
    # (binary flags are pinned to "off", so an absent flag never shows up as a reason)
    flags = {"pairs", "cardinal", "no_carrier", "len_dev", "homophones", "teen_ten", "competing"}
    ref = []
    for j, n in enumerate(FEATURES):
        col = X[y == 0, j]
        col = col[~np.isnan(col)]
        ref.append(0.0 if n in flags or len(col) == 0 else float(np.median(col)))
    MODEL_OUT.write_text(json.dumps({
        "version": 3, "features": FEATURES, "mean": [round(float(v), 6) for v in mean],
        "std": [round(float(v), 6) for v in std], "weights": [round(float(v), 6) for v in w],
        "bias": round(b, 6), "threshold": round(thr, 4), "invalid_format_p": round(p_invalid, 4),
        "ref": [round(v, 6) for v in ref], "meta": meta,
    }, indent=2))
    print(f"wrote {MODEL_OUT.relative_to(ROOT)}")
    for n, wi in sorted(zip(FEATURES, w), key=lambda t: -abs(t[1])):
        print(f"  {n:<13}{wi:+.3f}")
    print("baseline thresholds:", meta["baselines"])


if __name__ == "__main__":
    main()
