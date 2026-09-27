from pathlib import Path

import pytest

from trajscan.schema import Assessment, load_persona, make_transcript_id, parse_transcript_id

PERSONAS_DIR = Path(__file__).parent.parent / "personas"


def test_transcript_id_round_trip() -> None:
    transcript_id = make_transcript_id("overt_evader", 3, "style-plain")
    assert transcript_id == "overt_evader__seed03__style-plain"
    assert parse_transcript_id(transcript_id) == ("overt_evader", 3, "style-plain")


def test_transcript_id_default_variant() -> None:
    assert make_transcript_id("grad_student", 0) == "grad_student__seed00__base"


@pytest.mark.parametrize(
    "bad_id",
    [
        "grad_student__seed1__base",  # seed not zero-padded
        "grad_student_seed01_base",  # single-underscore separators
        "Grad_Student__seed01__base",  # uppercase
        "grad_student__seed01__",  # empty variant
    ],
)
def test_parse_rejects_malformed_ids(bad_id: str) -> None:
    with pytest.raises(ValueError):
        parse_transcript_id(bad_id)


def test_make_rejects_seed_over_two_digits() -> None:
    with pytest.raises(ValueError):
        make_transcript_id("grad_student", 100)


@pytest.mark.parametrize("path", sorted(PERSONAS_DIR.glob("*.yaml")), ids=lambda p: p.stem)
def test_persona_files_load(path: Path) -> None:
    persona = load_persona(path.stem, PERSONAS_DIR)
    # The ID format uses "__" as a separator, so persona ids must not contain it.
    assert "__" not in persona.id


def test_assessment_fields_have_descriptions() -> None:
    # Scout's structured answers require a description on every field.
    for name, field in Assessment.model_fields.items():
        assert field.description, f"Assessment.{name} has no description"
