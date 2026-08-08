import pytest
from django.core.management.base import CommandError

from apps.classes.management.commands.probe_exam_prep_mistral_solution_gap_crops import (
    _parse_specs,
)


def test_solution_gap_crop_specs_are_one_based_and_deduplicated():
    assert _parse_specs('33:left,34:right,33:left') == (
        (33, 'left'),
        (34, 'right'),
    )


def test_solution_gap_crop_specs_reject_unknown_side():
    with pytest.raises(CommandError):
        _parse_specs('33:middle')
