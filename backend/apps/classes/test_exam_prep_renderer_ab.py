import pytest

from django.core.management.base import CommandError

from apps.classes.management.commands.probe_exam_prep_renderer_ab import (
    _DEFAULT_ITEM_IDS,
    _parse_item_ids,
    _target_rows,
)


def test_renderer_ab_defaults_cover_known_render_risk_regions():
    assert _DEFAULT_ITEM_IDS == (
        "q-122",
        "s-046",
        "s-055",
        "s-056",
        "s-057",
        "s-065",
        "s-073",
        "s-081",
        "s-115",
        "s-150",
    )
    rows = _target_rows(_DEFAULT_ITEM_IDS)
    assert tuple(row.item_id for row in rows) == _DEFAULT_ITEM_IDS


def test_renderer_ab_item_parser_is_deterministic_and_validated():
    assert _parse_item_ids("s-057,q-122,s-057") == ("s-057", "q-122")
    with pytest.raises(CommandError, match="Unknown gold item ids"):
        _parse_item_ids("s-057,q-999")


def test_renderer_ab_empty_items_uses_frozen_defaults():
    assert _parse_item_ids("") == _DEFAULT_ITEM_IDS
