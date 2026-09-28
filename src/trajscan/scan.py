"""Stage 3 runner: every scanner x every configured model, one scan per model.

    python -m trajscan.scan                                  # models from configs/scan.yaml
    python -m trajscan.scan --models openrouter/openai/gpt-6-luna --where "task_id LIKE '%base'"

Each completed scan is appended to `scans/manifest.yaml` (path, model, filter),
which `python -m trajscan.validate` reads by default, so the set of scans
behind a result is recorded rather than remembered. Scanner refusals and
errors are recorded as outcomes; a scan with errors is still completed.
"""

import argparse
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from inspect_scout import scan, scan_complete, transcripts_from

from trajscan.scanners import SCANNERS

MANIFEST = Path("scans/manifest.yaml")


def read_manifest(path: Path = MANIFEST) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return yaml.safe_load(path.read_text()) or []


def run(models: list[str], transcripts: Path, where: str | None, scans: Path) -> None:
    source = transcripts_from(str(transcripts))
    if where:
        source = source.where(where)
    manifest = read_manifest()
    for model in models:
        print(f"== scanning with {model}")
        status = scan(
            scanners={name: factory() for name, factory in SCANNERS.items()},
            transcripts=source,
            scans=str(scans),
            model=model,
            display="plain",
        )
        if not status.complete:
            status = scan_complete(status.location)  # record errors as outcomes
        manifest.append(
            {
                "scan": status.location,
                "model": model,
                "where": where,
                "created": datetime.now(UTC).isoformat(timespec="seconds"),
            }
        )
        MANIFEST.write_text(yaml.safe_dump(manifest, sort_keys=False))
        print(f"   -> {status.location}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=Path, default=Path("configs/scan.yaml"))
    parser.add_argument("--models", help="comma-separated; overrides the config")
    parser.add_argument("--transcripts", type=Path, default=Path("logs/perturbed"))
    parser.add_argument("--where", default="task_id LIKE '%base'", help="SQL filter on transcripts")
    parser.add_argument("--scans", type=Path, default=Path("scans"))
    args = parser.parse_args()
    models = (
        args.models.split(",") if args.models else yaml.safe_load(args.config.read_text())["models"]
    )
    run(models, args.transcripts, args.where or None, args.scans)


if __name__ == "__main__":
    main()
