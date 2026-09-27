import pandas as pd

from trajscan.validate import refusal_summary


def test_refusal_summary_counts_each_point() -> None:
    preds = pd.DataFrame(
        {
            "transcript_id": ["a__seed00__base", "a__seed01__base", "b__seed00__base"],
            "persona": ["a", "a", "b"],
            "true_risk": [1, 1, 4],
            "user_source": ["simulated", "simulated", "scripted"],
            "generation_refusal": [None, "user_simulator", "target"],
            "predicted_risk": ["1", "refused", "refused"],
        }
    )
    summary = refusal_summary(preds)

    a = summary.loc[("a", 1, "simulated")]
    assert a["n"] == 2
    assert a["simulator_refused"] == 0.5
    assert a["target_refused"] == 0.0
    assert a["scanner_refused"] == 0.5

    b = summary.loc[("b", 4, "scripted")]
    assert (b["target_refused"], b["scanner_refused"]) == (1.0, 1.0)
