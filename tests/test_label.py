from pathlib import Path

import pandas as pd
import pytest

from trajscan.label import KEY_FILE, export, score
from trajscan.schema import load_persona, parse_transcript_id

LOGS = Path(__file__).parent.parent / "logs" / "raw"


@pytest.mark.skipif(not list(LOGS.glob("*.eval")), reason="no committed logs")
def test_export_is_blind_and_scores_round_trip(tmp_path: Path) -> None:
    export(LOGS, tmp_path, per_persona=1, seed=0)
    sheet = (tmp_path / "transcripts.md").read_text()
    key = pd.read_csv(tmp_path / KEY_FILE)
    # Blinding: no transcript ID (which names the persona) appears in the sheet.
    assert "__seed" not in sheet
    assert all(tid not in sheet for tid in key["transcript_id"])

    # Filling in the ground truth gives perfect agreement with ground truth.
    labels = pd.read_csv(tmp_path / "labels.csv")
    personas = key["transcript_id"].map(lambda t: load_persona(parse_transcript_id(t)[0]))
    labels["risk_level"] = [p.ground_truth_risk for p in personas]
    labels["threat_category"] = [p.threat_category for p in personas]
    labels["recognized"] = "n"
    labels.to_csv(tmp_path / "labels.csv", index=False)

    preds = key.assign(scanner="whole_transcript", predicted_risk="1")
    preds.to_csv(tmp_path / "preds.csv", index=False)
    result = score(tmp_path, tmp_path / "preds.csv").set_index(["comparison", "group"])
    row = result.loc[("self vs ground truth", "all")]
    assert (row["exact"], row["category_agreement"]) == (1.0, 1.0)
