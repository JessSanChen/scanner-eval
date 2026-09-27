"""Stage 4: compare scanner predictions to persona ground truth.

Joins scan results to personas and to generation metadata on the transcript
ID. A scanner refusal is its own predicted outcome ("refused"), not a missing
row: a scanner that goes silent on concerning logs is a failure mode worth
measuring. Refusals are reported at all three points: user simulator, target,
and scanner.

    python -m trajscan.validate --scan scans/scan_id=... --logs logs/perturbed --out results
"""

import argparse
import json
from pathlib import Path

import pandas as pd
from inspect_ai.log import read_eval_log
from inspect_scout import scan_results_df

from trajscan.schema import load_persona, parse_transcript_id


def predictions(scan_dir: Path, scanner: str = "whole_transcript") -> pd.DataFrame:
    results = scan_results_df(str(scan_dir)).scanners[scanner]
    rows = []
    for _, r in results.iterrows():
        persona_id, seed, variant = parse_transcript_id(r["transcript_task_id"])
        # Scout sets scan_error_type only for some failures (e.g. "refusal").
        if pd.notna(r["scan_error"]):
            refused = pd.notna(r["scan_error_type"]) and r["scan_error_type"] == "refusal"
            predicted = "refused" if refused else "error"
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


def generation_metadata(logs_dir: Path) -> pd.DataFrame:
    """Per-transcript metadata recorded by the generator (user source, refusals)."""
    rows = [
        {
            "transcript_id": sample.id,
            "user_source": sample.metadata.get("user_source"),
            "generation_refusal": sample.metadata.get("refusal"),
            "turns_completed": sample.metadata.get("turns_completed"),
        }
        for path in sorted(logs_dir.glob("*.eval"))
        for sample in read_eval_log(str(path)).samples or []
    ]
    return pd.DataFrame(rows)


def refusal_summary(preds: pd.DataFrame) -> pd.DataFrame:
    """Fraction of transcripts refused at each point, per persona."""
    flags = preds.assign(
        simulator_refused=preds["generation_refusal"] == "user_simulator",
        # NaN where the simulator refused first: the target never got a turn.
        target_refused=(preds["generation_refusal"] == "target").where(
            preds["generation_refusal"] != "user_simulator"
        ),
        # NaN (not 0) where no transcript existed: the scanner never got a chance.
        scanner_refused=(preds["predicted_risk"] == "refused").where(
            preds["predicted_risk"] != "no_transcript"
        ),
    )
    return flags.groupby(["persona", "true_risk", "user_source"]).agg(
        n=("transcript_id", "size"),
        simulator_refused=("simulator_refused", "mean"),
        target_refused=("target_refused", "mean"),
        scanner_refused=("scanner_refused", "mean"),
    )


def latest_scan(scans_dir: Path) -> Path:
    return max(scans_dir.glob("scan_id=*"), key=lambda p: p.stat().st_mtime)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--scan", type=Path, help="scan directory (default: latest in scans/)")
    parser.add_argument("--logs", type=Path, default=Path("logs/perturbed"))
    parser.add_argument("--out", type=Path, default=Path("results"))
    args = parser.parse_args()

    scan_dir = args.scan or latest_scan(Path("scans"))
    preds = predictions(scan_dir).merge(
        generation_metadata(args.logs), on="transcript_id", how="left", validate="one_to_one"
    )
    # Generation was refused before any exchange: nothing existed to scan (Scout
    # errors on empty transcripts), so this isn't a scanner outcome at all.
    preds.loc[preds["turns_completed"] == 0, "predicted_risk"] = "no_transcript"
    refusals = refusal_summary(preds)
    args.out.mkdir(parents=True, exist_ok=True)
    preds.to_csv(args.out / "predictions.csv", index=False)
    refusals.to_csv(args.out / "refusals.csv")

    print(f"scan: {scan_dir}\n")
    print("Confusion matrix (rows: true risk, columns: predicted):")
    print(pd.crosstab(preds["true_risk"], preds["predicted_risk"]), "\n")
    print("Refusal rate at each point, per persona:")
    print(refusals.to_string())


if __name__ == "__main__":
    main()
