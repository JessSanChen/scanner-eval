from pathlib import Path

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
