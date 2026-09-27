"""Hard rule: a persona's hidden objective never reaches the scanner.

Loads every committed log with the scanner's own content filter (what Scout
would hand `llm_scanner`) and checks no hidden objective appears in it.
"""

import asyncio
from pathlib import Path

import pytest
from inspect_scout import Transcript, transcripts_from

# Private Scout helper: reads the content filter registered by @scanner, so this
# test follows the scanner if its declared content ever changes.
from inspect_scout._scanner.scanner import config_for_scanner

from trajscan.scanners import whole_transcript
from trajscan.schema import load_persona

ROOT = Path(__file__).parent.parent
LOG_DIRS = [ROOT / "logs" / "raw", ROOT / "logs" / "perturbed"]
OBJECTIVES = [
    load_persona(path.stem, ROOT / "personas").hidden_objective.strip()
    for path in (ROOT / "personas").glob("*.yaml")
]
LOGS = [path for log_dir in LOG_DIRS for path in sorted(log_dir.glob("*.eval"))]


async def _read_as_scanner(log: Path) -> list[Transcript]:
    content = config_for_scanner(whole_transcript()).content
    async with transcripts_from(str(log)).reader() as reader:
        return [await reader.read(info, content) async for info in reader.index()]


@pytest.mark.skipif(not LOGS, reason="no committed logs")
@pytest.mark.parametrize("log", LOGS, ids=lambda p: f"{p.parent.name}/{p.name[:19]}")
def test_no_hidden_objective_in_scanner_input(log: Path) -> None:
    for transcript in asyncio.run(_read_as_scanner(log)):
        visible = "\n".join(m.text for m in transcript.messages) + str(transcript.metadata)
        assert not [m for m in transcript.messages if m.role == "system"]
        for objective in OBJECTIVES:
            # A distinctive 60-character slice, so paraphrase-free copying is caught.
            assert objective[:60] not in visible, f"objective leaked in {transcript.task_id}"
