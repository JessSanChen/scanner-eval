"""Stage 2: metamorphic perturbations of generated logs.

Each perturbation changes a transcript in a way that should NOT change the
correct verdict; validation reports how often the scanner's verdict flips.

Implemented (deterministic, no model calls, so they cannot be refused):

- `pad-pre2` / `pad-post2`: insert 2 benign exchanges before / after the
  conversation, taken from a donor persona's refusal-free conversations.
  Tests signal dilution and position in long, mixed logs.

Possible extensions: LLM style rewrites of user turns (non-native, terse,
formal), and moving or removing planted-marker turns (needs planted markers).

Output logs contain every base sample unchanged plus its perturbed variants,
with IDs `{persona}__seed{NN}__{variant}`.

    python -m trajscan.perturb --in logs/raw --out logs/perturbed
"""

import argparse
import hashlib
import uuid
from collections.abc import Callable
from pathlib import Path

import numpy as np
from inspect_ai.log import EvalSample, read_eval_log, write_eval_log
from inspect_ai.model import ChatMessage

from trajscan.scanners import split_exchanges
from trajscan.schema import make_transcript_id, parse_transcript_id

DONOR_PERSONA = "diagnostic_lab_tech"
PAD_EXCHANGES = 2

Exchange = list[ChatMessage]
Perturbation = Callable[[list[Exchange], list[Exchange]], list[Exchange]]

PERTURBATIONS: dict[str, Perturbation] = {
    "pad-pre2": lambda exchanges, padding: padding + exchanges,
    "pad-post2": lambda exchanges, padding: exchanges + padding,
}


def donor_exchanges(samples: list[EvalSample]) -> list[tuple[str, Exchange]]:
    """Complete (user + reply) exchanges from refusal-free donor conversations."""
    return [
        (str(s.id), exchange)
        for s in samples
        if parse_transcript_id(str(s.id))[0] == DONOR_PERSONA and not s.metadata.get("refusal")
        for exchange in split_exchanges(s.messages)
        if len(exchange) == 2
    ]


def _rng_for(transcript_id: str) -> np.random.Generator:
    # Deterministic per transcript, independent of file order.
    return np.random.default_rng(int(hashlib.sha256(transcript_id.encode()).hexdigest()[:8], 16))


def perturb_sample(sample: EvalSample, donors: list[tuple[str, Exchange]]) -> list[EvalSample]:
    base_id = str(sample.id)
    persona, seed, _ = parse_transcript_id(base_id)
    pool = [(did, ex) for did, ex in donors if did != base_id]  # never pad with itself
    if not sample.messages or len(pool) < PAD_EXCHANGES:
        return []
    picks = _rng_for(base_id).choice(len(pool), size=PAD_EXCHANGES, replace=False)
    padding = [pool[i][1] for i in picks]
    exchanges = split_exchanges(sample.messages)

    variants = []
    for name, perturb in PERTURBATIONS.items():
        messages = [m for exchange in perturb(exchanges, padding) for m in exchange]
        variants.append(
            sample.model_copy(
                update={
                    "id": make_transcript_id(persona, seed, name),
                    "uuid": uuid.uuid4().hex,  # Scout keys transcripts by sample uuid
                    "messages": messages,
                    # Recorded events describe the original conversation, not this one.
                    "events": [],
                    "metadata": {
                        **sample.metadata,
                        "perturbation": name,
                        "base_id": base_id,
                        "donor_ids": [pool[i][0] for i in picks],
                    },
                },
                deep=True,
            )
        )
    return variants


def perturb_logs(in_dir: Path, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    logs = {path: read_eval_log(str(path)) for path in sorted(in_dir.glob("*.eval"))}
    donors = donor_exchanges([s for log in logs.values() for s in log.samples or []])
    written = []
    for path, log in logs.items():
        base = log.samples or []
        log.samples = base + [v for s in base for v in perturb_sample(s, donors)]
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
