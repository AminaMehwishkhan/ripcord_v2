import json

import pytest

from app import benchmark as bm
from app.benchmark import (
    auroc, bootstrap_ci, evaluate, load_items, make_policies, operating_curve, rate, reliability, run_item, summarise,
)
from tests.conftest import toy_model


# ---- metrics ---------------------------------------------------------------------

def test_auroc_perfect_random_and_inverted():
    assert auroc([0.9, 0.8, 0.2, 0.1], [1, 1, 0, 0]) == 1.0
    assert auroc([0.1, 0.2, 0.8, 0.9], [1, 1, 0, 0]) == 0.0
    assert auroc([0.5, 0.5, 0.5, 0.5], [1, 0, 1, 0]) == 0.5


def test_auroc_needs_both_classes():
    assert auroc([0.1, 0.2], [0, 0]) is None


def test_bootstrap_interval_contains_the_mean_and_shrinks_with_more_data():
    small = [1.0] * 5 + [0.0] * 5
    big = small * 20
    lo_s, hi_s = bootstrap_ci(small)
    lo_b, hi_b = bootstrap_ci(big)
    assert lo_s <= 0.5 <= hi_s and lo_b <= 0.5 <= hi_b
    assert (hi_b - lo_b) < (hi_s - lo_s)


def test_rate_reports_value_interval_and_n():
    r = rate([1.0, 0.0, 0.0, 1.0])
    assert r["value"] == 0.5 and r["n"] == 4 and r["ci"][0] <= 0.5 <= r["ci"][1]


def test_reliability_is_zero_when_perfectly_calibrated():
    preds = [0.1] * 10 + [0.9] * 10
    labels = [1] + [0] * 9 + [1] * 9 + [0]
    assert reliability(preds, labels)["ece"] == pytest.approx(0.0, abs=1e-6)


def test_operating_curve_is_monotone():
    curve = operating_curve([0.9, 0.7, 0.4, 0.2, 0.1], [1, 1, 0, 1, 0])
    catch = [p["catch"] for p in curve]
    assert catch == sorted(catch, reverse=True)
    assert curve[0]["catch"] == 1.0 and curve[0]["false_alarm"] == 1.0


# ---- running a recorded utterance through the real pipeline -------------------------

def w(text, conf):
    return {"text": text, "confidence": conf, "start": 0, "end": 0, "word_is_final": True}


def item(truth, heard_words, reply_no=None, condition="clean", id="t0"):
    spoken = {"1": "one", "5": "five", "8": "eight", "0": "zero", "3": "three", "7": "seven"}
    return {
        "id": id, "split": "test", "speaker": 1, "true_value": truth, "condition": condition,
        "asr": {"transcript": " ".join(t for t, _ in heard_words), "words": [w(t, c) for t, c in heard_words]},
        "reply_yes": {"transcript": "yes that's right", "words": [w("yes", .95), w("that's", .95), w("right", .95)]},
        "reply_no": reply_no or {
            "transcript": "no it's " + " ".join(spoken[d] for d in truth),
            "words": [w("no", .95), w("it's", .95)] + [w(spoken[d], .95) for d in truth]},
    }


GOOD = [("my", .95), ("order", .95), ("number", .95), ("is", .95), ("one", .95), ("five", .95), ("eight", .95), ("zero", .95)]
BAD = [("my", .95), ("order", .95), ("number", .95), ("is", .95), ("one", .5), ("five", .3), ("seven", .4), ("zero", .95)]   # heard 1570


def policies():
    return make_policies(toy_model(), 0.8, 0.7)


def test_no_check_accepts_a_wrong_number_silently():
    r = run_item(item("1580", BAD), policies()["no_check"])
    assert r["outcome"] == "wrong" and r["final"] == "1570" and r["asked"] is False


def test_ripcord_catches_it_and_recovers_the_right_number():
    r = run_item(item("1580", BAD), policies()["ripcord_v2"])
    assert r["asked"] is True
    assert r["outcome"] == "correct" and r["final"] == "1580"


def test_ripcord_leaves_a_clean_call_alone():
    r = run_item(item("1580", GOOD), policies()["ripcord_v2"])
    assert r["asked"] is False and r["outcome"] == "correct" and r["questions"] == 0


def test_always_confirm_asks_even_when_it_was_right():
    r = run_item(item("1580", GOOD), policies()["always_confirm"])
    assert r["asked"] is True and r["outcome"] == "correct"


def test_a_call_with_no_number_is_unresolved_not_wrong():
    nothing = item("1580", [("hello", .9), ("there", .9)])
    assert run_item(nothing, policies()["ripcord_v2"])["outcome"] == "unresolved"


def test_summary_separates_misheard_from_clean_calls():
    items = [item("1580", GOOD, id="a"), item("1580", BAD, id="b")]
    runs = [run_item(i, policies()["no_check"]) for i in items]
    s = summarise(runs)
    assert s["misheard_calls"] == 1 and s["clean_capture_calls"] == 1
    assert s["wrong_action"]["value"] == 0.5
    assert s["error_catch_rate"]["value"] == 0.0 and s["false_alarm_rate"]["value"] == 0.0
    assert s["silent_catch_rate"]["value"] == 0.0     # the wrong number was a valid-looking 4 digits


def test_evaluate_ranks_ripcord_above_no_check():
    items = [item("1580", GOOD, id=f"g{i}") for i in range(6)] + [item("1580", BAD, id=f"b{i}") for i in range(6)]
    res = evaluate(items, toy_model(), 0.8, 0.7)
    p = res["policies"]
    assert p["ripcord_v2"]["wrong_action"]["value"] < p["no_check"]["wrong_action"]["value"]
    assert p["ripcord_v2"]["questions_per_call"]["value"] < p["always_confirm"]["questions_per_call"]["value"]
    assert res["auroc"]["ripcord_v2"] == 1.0
    assert set(res["auroc_valid_format"]) == set(res["auroc"])
    assert res["capture_error_rate"] == 0.5


# ---- the recorded dataset (only when it has been generated) ---------------------------

ITEMS = load_items()


@pytest.mark.skipif(not ITEMS, reason="benchmark data not generated")
class TestDataset:
    def test_splits_never_share_a_speaker_or_a_number(self):
        by = {}
        for it in ITEMS:
            by.setdefault(it["split"], []).append(it)
        for a in by:
            for b in by:
                if a < b:
                    assert not ({i["speaker"] for i in by[a]} & {i["speaker"] for i in by[b]}), (a, b, "speakers")
                    assert not ({i["true_value"] for i in by[a]} & {i["true_value"] for i in by[b]}), (a, b, "numbers")

    def test_every_item_carries_real_confidences(self):
        for it in ITEMS[:200]:
            ws = it["asr"]["words"]
            assert all(0.0 <= x["confidence"] <= 1.0 for x in ws)
            assert it["true_value"].isdigit() and len(it["true_value"]) == 4

    def test_results_file_is_consistent_with_the_dataset(self):
        if not bm.RESULTS_PATH.exists():
            pytest.skip("no benchmark results yet")
        res = json.loads(bm.RESULTS_PATH.read_text())
        test_n = sum(1 for i in ITEMS if i["split"] == "test")
        assert res["split"] == "test" and res["n_calls"] == test_n


# ---- importing transcripts from another recogniser --------------------------------------

def test_import_transcripts_converts_assemblyai_style_json(tmp_path):
    import csv
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "benchmark"))
    import import_transcripts as imp

    (tmp_path / "a.json").write_text(json.dumps({"text": "My order number is one five eight zero", "words": [
        {"text": "My", "start": 10, "end": 200, "confidence": 0.98},
        {"text": "one", "start": 300, "end": 400, "confidence": 0.5}]}))
    row = {"id": "r1", "split": "test", "speaker": "s9", "true_value": "1580", "condition": "clean",
           "main": "a.json", "yes": "", "no": ""}
    it = imp.build_item(row, tmp_path)
    assert it["asr"]["words"][1]["confidence"] == 0.5 and it["asr"]["transcript"].startswith("my order")
    assert it["reply_yes"] is None and it["true_value"] == "1580"
    with pytest.raises(ValueError):
        imp.build_item({**row, "split": "dev"}, tmp_path)
    with pytest.raises(ValueError):
        imp.build_item({**row, "true_value": "15x0"}, tmp_path)
    # and the converted item runs through the real pipeline
    assert bm.entity_of(it) is not None
