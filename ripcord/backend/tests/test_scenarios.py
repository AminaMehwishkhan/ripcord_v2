import json
from pathlib import Path

import pytest

from app.evaluation import run_evaluation
from app.mock_service import RECORDED_PATH, load_scenarios, reply_turn, stream_scenario
from app.session import SessionOrchestrator

SCRIPTED = [s for s in load_scenarios() if s["source"] == "scripted"]


def run(scenario, ripcord):
    orch = SessionOrchestrator(ripcord_enabled=ripcord, mock_mode=True)
    for i, t in enumerate(scenario["turns"]):
        orch.process_turn({"transcript": t["transcript"], "end_of_turn": True, "turn_order": i, "words": t["words"]})
    return orch


def test_there_are_ten_scripted_scenarios():
    assert len(SCRIPTED) == 10


@pytest.mark.parametrize("scenario", SCRIPTED, ids=lambda s: f"scripted_{s['id']}")
def test_ripcord_never_ends_on_a_wrong_number(scenario):
    truth = scenario["expect"]["final_value"]
    orch = run(scenario, ripcord=True)
    if truth is None:                       # e.g. audio cut off mid-number: it must NOT guess
        assert orch.state.verified_value is None
    else:
        # Ripcord may pause and wait for the caller's answer, but it must never settle on a wrong number
        assert orch.state.verified_value in (None, truth)


def test_a_clear_number_is_not_interrupted():
    for sid in (1, 7):
        sc = next(s for s in SCRIPTED if s["id"] == sid)
        orch = run(sc, ripcord=True)
        assert orch.questions_asked == 0 and orch.state.verified_value == sc["expect"]["final_value"]


def test_a_misheard_and_a_cut_off_number_are_both_stopped():
    for sid in (2, 8):
        sc = next(s for s in SCRIPTED if s["id"] == sid)
        orch = run(sc, ripcord=True)
        assert orch.questions_asked >= 1 and orch.state.verified_value is None


def test_without_ripcord_the_misheard_number_is_acted_on():
    sc = next(s for s in SCRIPTED if s["id"] == 2)
    orch = run(sc, ripcord=False)
    assert orch.state.verified_value == sc["expect"]["wrong_value_accepted"]


def test_legacy_evaluation_report_is_internally_consistent():
    report = run_evaluation()
    assert report["scenario_count"] == len(SCRIPTED)
    wrong_a = sum(r["mode_a_wrong"] for r in report["per_scenario"])
    wrong_b = sum(r["mode_b_wrong"] for r in report["per_scenario"])
    assert wrong_b <= wrong_a
    assert report["entity_errors_without_ripcord"].startswith(str(wrong_a))
    assert report["entity_errors_with_ripcord"].startswith(str(wrong_b))


# ---- recorded demos (real recogniser output) ---------------------------------------------

RECORDED = [s for s in load_scenarios() if s["source"] == "recorded"]


@pytest.mark.skipif(not RECORDED, reason="demo/recorded_scenarios.json not generated")
class TestRecorded:
    def test_ids_do_not_clash_with_scripted_ones(self):
        ids = [s["id"] for s in load_scenarios()]
        assert len(ids) == len(set(ids))
        assert all(s["id"] >= 100 for s in RECORDED)

    def test_each_clip_is_real_output_with_ground_truth(self):
        for s in RECORDED:
            assert s["turns"][0]["words"] and all("confidence" in w for w in s["turns"][0]["words"])
            assert len(s["expect"]["final_value"]) == 4 and s["category"]

    def test_clips_come_from_the_validation_split_not_the_test_split(self):
        from app.benchmark import load_items
        items = {i["id"]: i for i in load_items()}
        if not items:
            pytest.skip("benchmark data not present")
        assert all(items[s["clip_id"]]["split"] == "val" for s in RECORDED)

    def test_the_miss_category_is_really_a_miss(self):
        misses = [s for s in RECORDED if s["category"] == "confidently-wrong"]
        for s in misses:
            assert s["expect"]["heard"] != s["expect"]["final_value"]
            assert s["expect"]["ripcord_asked"] is False

    def test_replays_through_the_websocket_pipeline(self):
        sc = RECORDED[0]
        orch = run(sc, ripcord=True)
        assert orch.state.entity is not None or orch.state.verified_value is not None


def test_reply_turn_is_none_for_scripted_scenarios():
    assert reply_turn(SCRIPTED[0], "yes") is None
