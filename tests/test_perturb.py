from inspect_ai.log import EvalSample
from inspect_ai.model import ChatMessageAssistant, ChatMessageUser

from trajscan.perturb import donor_exchanges, perturb_sample


def _sample(sample_id: str, turns: list[str], refusal: str | None = None) -> EvalSample:
    messages = []
    for t in turns:
        messages += [ChatMessageUser(content=f"{t}?"), ChatMessageAssistant(content=f"{t}.")]
    return EvalSample(
        id=sample_id,
        epoch=1,
        input="x",
        target="",
        messages=messages,
        metadata={"refusal": refusal},
        uuid=f"uuid-{sample_id}",
    )


DONORS = donor_exchanges(
    [
        _sample("diagnostic_lab_tech__seed00__base", ["d0a", "d0b"]),
        _sample("diagnostic_lab_tech__seed01__base", ["d1a", "d1b"]),
        _sample("diagnostic_lab_tech__seed02__base", ["refused"], refusal="target"),  # excluded
        _sample("grad_student__seed00__base", ["g"]),  # not the donor persona
    ]
)


def test_donor_pool_is_refusal_free_donor_exchanges() -> None:
    texts = sorted(ex[0].text for _, ex in DONORS)
    assert texts == ["d0a?", "d0b?", "d1a?", "d1b?"]


def test_padding_position_ids_and_metadata() -> None:
    base = _sample("overt_evader__seed03__base", ["x"])
    pre, post = perturb_sample(base, DONORS)

    assert pre.id == "overt_evader__seed03__pad-pre2"
    assert post.id == "overt_evader__seed03__pad-post2"
    assert [m.text for m in pre.messages][-2:] == ["x?", "x."]  # original at the end
    assert [m.text for m in post.messages][:2] == ["x?", "x."]  # original at the start
    assert len(pre.messages) == 2 + 2 * 2
    assert pre.uuid != base.uuid and pre.uuid != post.uuid
    assert pre.metadata["base_id"] == base.id and pre.events == []
    assert base.messages[0].text == "x?"  # the base sample is not mutated


def test_padding_is_deterministic_and_never_self() -> None:
    donor = _sample("diagnostic_lab_tech__seed00__base", ["d0a", "d0b"])
    first = perturb_sample(donor, DONORS)
    again = perturb_sample(donor, DONORS)
    assert [m.text for m in first[0].messages] == [m.text for m in again[0].messages]
    assert all(did != donor.id for did in first[0].metadata["donor_ids"])


def test_empty_transcript_is_not_perturbed() -> None:
    assert perturb_sample(_sample("fragmenter__seed00__base", []), DONORS) == []
