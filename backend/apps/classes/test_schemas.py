"""Unit tests for the structure-stage Pydantic schemas (services/schemas.py).

The load-bearing invariant (ref: llm-structure-stage.md): ``StructureOutput.outline``
is a list of sections, each with a ``units`` list — exactly what asset reinjection
and ``sync_structure_from_session`` iterate over. Everything else stays soft
(``extra='allow'``). These are the shapes ``validate_keep_dict`` gates on.
"""
import pytest
from pydantic import ValidationError

from apps.classes.services.schemas import (
    StructureOutput,
    StructureSection,
    StructureUnit,
    StructureRootObject,
)

pytestmark = pytest.mark.unit


def test_full_valid_structure_validates():
    obj = StructureOutput.model_validate({
        'root_object': {
            'title': 'Algebra',
            'target_audience_level': 'grade 10',
            'what_you_will_learn': ['x', 'y'],
        },
        'outline': [
            {'id': 's1', 'title': 'Sec 1', 'units': [
                {'id': 'u1', 'title': 'Unit 1', 'merrill_type': 'demonstration',
                 'source_markdown': 'src', 'content_markdown': 'body',
                 'image_ideas': ['a plot']},
            ]},
        ],
    })
    assert obj.root_object.title == 'Algebra'
    assert obj.outline[0].units[0].id == 'u1'
    assert obj.outline[0].units[0].image_ideas == ['a plot']


def test_outline_defaults_to_empty_list():
    obj = StructureOutput.model_validate({'root_object': {'title': 'T'}})
    assert obj.outline == []


def test_section_units_default_to_empty_list():
    sec = StructureSection.model_validate({'id': 's', 'title': 'S'})
    assert sec.units == []


def test_root_object_lists_default_empty():
    ro = StructureRootObject.model_validate({'title': 'T'})
    assert ro.what_you_will_learn == []


def test_extra_keys_are_allowed():
    """extra='allow' — new prompt fields don't break validation (the dict is kept)."""
    obj = StructureOutput.model_validate({
        'outline': [],
        'brand_new_field': {'nested': 1},
    })
    # extra fields survive on the model (extra='allow' stores them).
    assert obj.model_dump().get('brand_new_field') == {'nested': 1}


def test_outline_must_be_a_list():
    with pytest.raises(ValidationError):
        StructureOutput.model_validate({'outline': {'not': 'a list'}})


def test_section_units_must_be_a_list():
    with pytest.raises(ValidationError):
        StructureSection.model_validate({'id': 's', 'title': 'S', 'units': 'nope'})


def test_unit_image_ideas_must_be_a_list():
    with pytest.raises(ValidationError):
        StructureUnit.model_validate({'id': 'u', 'image_ideas': 'not-a-list'})
