"""Stage 4: compare scanner predictions to persona ground truth.

Joins scan results to personas on the transcript ID. A scanner refusal is its
own predicted outcome ("refused"), not a missing row: a scanner that goes
silent on concerning logs is a failure mode worth measuring.

    python -m trajscan.validate --scan scans/scan_id=... --out results
"""

import argparse
import json
from pathlib import Path

import pandas as pd
from inspect_scout import scan_results_df

from trajscan.schema import load_persona, parse_transcript_id


def predictions(scan_dir: Path, scanner: str = "whole_transcript") -> pd.DataFrame:
    results = scan_results_df(str(scan_dir)).scanners[scanner]
    rows = []
    for _, r in results.iterrows():
        persona_id, seed, variant = parse_transcript_id(r["transcript_task_id"])
        if pd.notna(r["scan_error_type"]):
            predicted = "refused" if r["scan_error_type"] == "refusal" else "error"
        else:
            predicted = str(json.loads(r["value"])["risk_level"])
        rows.append(
            {
                "transcript_id": r["transcript_task_id"],
                "persona": persona_id,
                "seed": seed,
                "variant": variant,
                "true_risk": load_persona(persona_id).ground_truth_risk,
                "predicted_risk": predicted,
            }
        )
    return pd.DataFrame(rows).sort_values("transcript_id", ignore_index=True)


def latest_scan(scans_dir: Path) -> Path:
    return max(scans_dir.glob("scan_id=*"), key=lambda p: p.stat().st_mtime)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--scan", type=Path, help="scan directory (default: latest in scans/)")
    parser.add_argument("--out", type=Path, default=Path("results"))
    args = parser.parse_args()

    scan_dir = args.scan or latest_scan(Path("scans"))
    preds = predictions(scan_dir)
    args.out.mkdir(parents=True, exist_ok=True)
    preds.to_csv(args.out / "predictions.csv", index=False)

    print(f"scan: {scan_dir}\n")
    print("Confusion matrix (rows: true risk, columns: predicted):")
    print(pd.crosstab(preds["true_risk"], preds["predicted_risk"]), "\n")
    refused = preds.assign(refused=preds["predicted_risk"] == "refused")
    print("Scanner refusal rate by true risk:")
    print(refused.groupby("true_risk")["refused"].mean())


if __name__ == "__main__":
    main()
