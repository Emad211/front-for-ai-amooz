from __future__ import annotations

import pytest

from apps.classes.services.exam_prep_mistral_page_batch_transcriber import PageBatchEnvelopeError
from apps.classes.services.exam_prep_mistral_page_batch_transcriber_v2 import (
    _normalize_items_envelope,
)


def test_normalize_accepts_canonical_items_object():
    raw = {"items": [{"target_id": "q-1"}]}
    assert _normalize_items_envelope(raw, target_count=1) is raw


def test_normalize_accepts_bare_item_array_losslessly():
    raw = [{"target_id": "q-1"}, {"target_id": "q-2"}]
    assert _normalize_items_envelope(raw, target_count=2) == {"items": raw}


def test_normalize_accepts_single_item_object_only_for_one_target():
    raw = {"target_id": "q-1", "kind": "question"}
    assert _normalize_items_envelope(raw, target_count=1) == {"items": [raw]}
    with pytest.raises(PageBatchEnvelopeError):
        _normalize_items_envelope(raw, target_count=2)


def test_normalize_rejects_unknown_wrapper_fail_closed():
    with pytest.raises(PageBatchEnvelopeError) as exc:
        _normalize_items_envelope({"results": []}, target_count=1)
    assert "object_keys=results" in exc.value.reason_code
