from pathlib import Path

import pytest
from inspect_ai.model import ChatMessageAssistant, ChatMessageUser

from trajscan.generate import KICKOFF, simulator_view
from trajscan.schema import load_persona

PERSONA = load_persona("overt_evader", Path(__file__).parent.parent / "personas")


def test_simulator_view_flips_roles() -> None:
    transcript = [
        ChatMessageUser(content="persona line 1"),
        ChatMessageAssistant(content="target reply 1"),
    ]
    view = simulator_view(PERSONA, transcript)

    assert [m.role for m in view] == ["system", "user", "assistant", "user"]
    assert view[1].text == KICKOFF
    assert view[2].text == "persona line 1"  # simulator's own line -> assistant
    assert view[3].text == "target reply 1"  # target's reply -> user


def test_objective_only_in_simulator_view() -> None:
    transcript = [ChatMessageUser(content="hi"), ChatMessageAssistant(content="hello")]
    view = simulator_view(PERSONA, transcript)

    assert PERSONA.hidden_objective.strip() in view[0].text
    # Building the view must not mutate or add to the real transcript.
    assert [m.text for m in transcript] == ["hi", "hello"]


def test_scripted_persona_sends_script_turns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from inspect_ai import eval as inspect_eval

    from trajscan.generate import persona_conversations

    (tmp_path / "personas").mkdir()
    (tmp_path / "personas" / "scripted_test.yaml").write_text(
        "id: scripted_test\n"
        "archetype: test\n"
        "hidden_objective: test objective\n"
        "ground_truth_risk: 1\n"
        "threat_category: none\n"
        "style: test\n"
        "script: [first line, second line]\n"
    )
    monkeypatch.chdir(tmp_path)

    [log] = inspect_eval(
        persona_conversations(personas="scripted_test", seeds=1),
        model="mockllm/model",
        log_dir=str(tmp_path / "logs"),
        display="none",
    )
    sample = log.samples[0]
    user_turns = [m.text for m in sample.messages if m.role == "user"]
    assert user_turns == ["first line", "second line"]  # script length, not `turns`
    assert sample.metadata["user_source"] == "scripted"
    assert sample.metadata["turns_completed"] == 2
