from typing import Any

import pandas as pd

from trajscan.validate import aggregate, refusal_summary


def _assessment(risk: int, threat: bool = False) -> dict[str, Any]:
    return {
        "risk_level": risk,
        "threat_present": threat,
        "threat_category": "oversight_evasion" if threat else "none",
        "confidence": 0.8,
        "evidence": [{"message_id": "M1"}] if threat else [],
        "recommended_action": "review" if threat else "no_action",
    }


def _units(*items: dict[str, Any] | str) -> pd.DataFrame:
    """Each item is an assessment dict (scored) or "refused"."""
    return pd.DataFrame(
        [
            {"outcome": "refused", "assessment": None}
            if item == "refused"
            else {"outcome": "scored", "assessment": item}
            for item in items
        ]
    )


def test_aggregate_flag_beats_refusal() -> None:
    verdict = aggregate(_units(_assessment(1), "refused", _assessment(4, threat=True)))
    assert verdict["predicted_risk"] == "4"
    assert verdict["predicted_category"] == "oversight_evasion"
    assert (verdict["units_scored"], verdict["units_refused"]) == (2, 1)


def test_aggregate_refusal_beats_low_scores() -> None:
    # A refused turn would go to review, so it outranks unflagged scores.
    assert aggregate(_units(_assessment(2), "refused"))["predicted_risk"] == "refused"


def test_aggregate_max_of_low_scores() -> None:
    assert aggregate(_units(_assessment(1), _assessment(2)))["predicted_risk"] == "2"


def test_aggregate_all_refused() -> None:
    verdict = aggregate(_units("refused", "refused"))
    assert verdict["predicted_risk"] == "refused"
    assert verdict["predicted_category"] is None


def test_refusal_summary_per_stage_and_scanner() -> None:
    base = {
        "transcript_id": ["a0", "a1", "b0"],
        "persona": ["a", "a", "b"],
        "true_risk": [1, 1, 4],
        "user_source": ["simulated", "simulated", "scripted"],
        "generation_refusal": [None, "user_simulator", "target"],
    }
    preds = pd.concat(
        [
            pd.DataFrame(
                {
                    **base,
                    "scanner": "whole_transcript",
                    "predicted_risk": ["1", "no_transcript", "refused"],
                }
            ),
            pd.DataFrame(
                {**base, "scanner": "per_turn", "predicted_risk": ["2", "no_transcript", "4"]}
            ),
        ],
        ignore_index=True,
    )
    summary = refusal_summary(preds)

    a = summary.loc[("a", 1, "simulated")]
    assert (a["n"], a["simulator_refused"]) == (2, 0.5)
    assert a["target_refused"] == 0.0  # the simulator-refused transcript is excluded
    assert a["scanner_refused:whole_transcript"] == 0.0  # no_transcript excluded

    b = summary.loc[("b", 4, "scripted")]
    assert b["target_refused"] == 1.0
    assert b["scanner_refused:whole_transcript"] == 1.0
    assert b["scanner_refused:per_turn"] == 0.0


def test_unit_outcomes_handles_scout_shapes() -> None:
    from trajscan.validate import unit_outcomes

    results = pd.DataFrame(
        {
            "transcript_task_id": ["t0", "t1", "t2", "t3", "t4", "t5"],
            # whole_transcript stores JSON strings; per_turn stores dicts; NA when unset.
            "value": ['{"risk_level": 1}', {"risk_level": 2}, pd.NA, None, pd.NA, pd.NA],
            "scan_error": [pd.NA, pd.NA, "refused", pd.NA, pd.NA, "boom"],
            "scan_error_type": [pd.NA, pd.NA, "refusal", pd.NA, pd.NA, pd.NA],
            "metadata.refused": [pd.NA, False, pd.NA, True, pd.NA, pd.NA],
        }
    )
    units = unit_outcomes(results)
    assert list(units["outcome"]) == [
        "scored",
        "scored",
        "refused",
        "refused",
        "no_answer",
        "error",
    ]
    assert units["assessment"][0] == {"risk_level": 1}
