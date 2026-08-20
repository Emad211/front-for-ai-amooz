from __future__ import annotations

from apps.classes.management.commands.replay_exam_prep_mistral_stage5 import _subset_layout
from apps.classes.management.commands.replay_exam_prep_mistral_visual_stage3 import _DiagnosticStore


def test_diagnostic_store_keeps_logical_key_but_uses_compact_local_path(tmp_path):
    root = tmp_path / ("very-long-root-" + "x" * 80)
    store = _DiagnosticStore(root)
    logical = (
        "exam-prep/source/visuals/v1/"
        + "a" * 64
        + "/q135-solution-01-"
        + "b" * 16
        + ".png"
    )

    returned = store.save(logical, b"png-bytes")

    assert returned == logical
    relative = store.files[logical]
    assert relative.startswith("objects/")
    assert len(relative) < 100
    # Read through store.root, not the raw `root`: on Windows the store swaps in
    # a \\?\-prefixed root so a deep --out directory cannot overflow MAX_PATH,
    # and rebuilding the path from the unprefixed root would hit that cap here.
    assert (store.root / relative).read_bytes() == b"png-bytes"


def test_targeted_layout_scope_keeps_only_requested_question_regions():
    layout = {
        "pages": [
            {
                "originalPageNumber": 13,
                "regions": [
                    {"questionNumber": 134, "kind": "solution"},
                    {"questionNumber": 135, "kind": "solution"},
                    {"questionNumber": 136, "kind": "solution"},
                ],
            },
            {
                "originalPageNumber": 15,
                "regions": [
                    {"questionNumber": 145, "kind": "solution"},
                ],
            },
        ]
    }

    scoped = _subset_layout(layout, numbers=frozenset({135}))

    assert len(scoped["pages"]) == 1
    assert scoped["pages"][0]["originalPageNumber"] == 13
    assert scoped["pages"][0]["regions"] == [
        {"questionNumber": 135, "kind": "solution"}
    ]
