"""Stage 2: apply metamorphic perturbations to generated logs.

M1: pass-through. Every log is read and rewritten unchanged (variant `base`),
which exercises the .eval read/write path the real perturbations will use.

    python -m trajscan.perturb --in logs/raw --out logs/perturbed
"""

import argparse
from pathlib import Path

from inspect_ai.log import read_eval_log, write_eval_log


def perturb_logs(in_dir: Path, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for path in sorted(in_dir.glob("*.eval")):
        log = read_eval_log(str(path))
        out_path = out_dir / path.name
        write_eval_log(log, str(out_path))
        written.append(out_path)
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--in", dest="in_dir", type=Path, default=Path("logs/raw"))
    parser.add_argument("--out", dest="out_dir", type=Path, default=Path("logs/perturbed"))
    args = parser.parse_args()
    for path in perturb_logs(args.in_dir, args.out_dir):
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
