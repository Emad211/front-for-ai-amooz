from __future__ import annotations

from types import SimpleNamespace

from apps.classes.services import exam_prep_mistral_native_answer_headings as native


def _reader():
    return SimpleNamespace(
        pages=[SimpleNamespace(mediabox=SimpleNamespace(height=1000, width=600))]
    )


def test_native_heading_parser_is_anchored_and_normalizes_digits():
    text = (
        "متن عادی گزینه ۲\n"
        "۲۵۱ - پاسخ تشریحی »۳«\n"
        "۲۵۲- هر متن کوتاه «۱»\n"
    )
    assert native._page_heading_pairs(text) == [(251, 3), (252, 1)]


def test_native_evidence_trust_requires_exact_unique_question_coverage():
    evidence = native.NativeAnswerEvidence(
        headings=(
            native.NativeAnswerHeading(1, 2, 10),
            native.NativeAnswerHeading(2, 4, 10),
        ),
        answer_pages=(10,),
        coordinate_complete_pages=(),
        duplicate_question_numbers=(),
        conflicting_question_numbers=(),
    )
    assert evidence.trusted_for([1, 2]) is True
    assert evidence.trusted_for([1, 2, 3]) is False


def test_overlay_uses_unique_geometry_per_heading_and_preserves_ambiguous_bbox(monkeypatch):
    monkeypatch.setattr(native, "PdfReader", lambda *_args, **_kwargs: _reader())
    evidence = native.NativeAnswerEvidence(
        headings=(
            native.NativeAnswerHeading(1, 2, 1),
            native.NativeAnswerHeading(2, 3, 1, side="left", x=200, y=600),
        ),
        answer_pages=(1,),
        coordinate_complete_pages=(),
        duplicate_question_numbers=(),
        conflicting_question_numbers=(),
    )
    root = {
        "pages": [
            {
                "index": 0,
                "sourcePhysicalPage": 1,
                "blocks": [
                    {
                        "type": "text",
                        "content": "1 - گزینه 4",
                        "x0": 0.6,
                        "y0": 0.1,
                        "x1": 0.9,
                        "y1": 0.12,
                    },
                    {
                        "type": "text",
                        "content": "2 - گزینه 4",
                        "x0": 0.1,
                        "y0": 0.4,
                        "x1": 0.4,
                        "y1": 0.42,
                    },
                    {
                        "type": "text",
                        "content": "بدنه پاسخ دو",
                        "x0": 0.1,
                        "y0": 0.43,
                        "x1": 0.4,
                        "y1": 0.5,
                    },
                ],
            }
        ]
    }
    output = native.overlay_native_solution_heading_blocks(
        root,
        pdf_data=b"pdf",
        evidence=evidence,
        trusted=True,
    )
    page = output["pages"][0]
    blocks = page["blocks"]
    assert page["nativeAnswerLabels"] == {"1": "2", "2": "3"}
    q1 = [block for block in blocks if block.get("nativeAnswerLabelOverride")]
    assert len(q1) == 1
    assert q1[0]["content"] == "1 - گزینه 2"
    assert q1[0]["y0"] == 0.1

    q2 = [block for block in blocks if block.get("nativeAnswerHeading")]
    assert len(q2) == 1
    assert q2[0]["content"] == "2 - گزینه 3"
    assert 0.38 < q2[0]["y0"] < 0.42
    assert any(block.get("content") == "بدنه پاسخ دو" for block in blocks)


def test_complete_native_page_removes_misnumbered_ocr_heading_noise(monkeypatch):
    monkeypatch.setattr(native, "PdfReader", lambda *_args, **_kwargs: _reader())
    evidence = native.NativeAnswerEvidence(
        headings=(
            native.NativeAnswerHeading(55, 2, 1, side="right", x=500, y=800),
            native.NativeAnswerHeading(56, 4, 1, side="right", x=500, y=600),
        ),
        answer_pages=(1,),
        coordinate_complete_pages=(1,),
        duplicate_question_numbers=(),
        conflicting_question_numbers=(),
    )
    root = {
        "pages": [
            {
                "index": 0,
                "blocks": [
                    {"type": "text", "content": "55 - گزینه 3", "x0": 0.6, "y0": 0.1, "x1": 0.9, "y1": 0.12},
                    {"type": "text", "content": "6 - گزینه 4", "x0": 0.6, "y0": 0.3, "x1": 0.9, "y1": 0.32},
                    {"type": "text", "content": "بدنه پاسخ", "x0": 0.6, "y0": 0.2, "x1": 0.9, "y1": 0.28},
                ],
            }
        ]
    }
    output = native.overlay_native_solution_heading_blocks(
        root,
        pdf_data=b"pdf",
        evidence=evidence,
        trusted=True,
    )
    blocks = output["pages"][0]["blocks"]
    contents = [block.get("content") for block in blocks]
    assert "55 - گزینه 3" not in contents
    assert "6 - گزینه 4" not in contents
    assert "55 - گزینه 2" in contents
    assert "56 - گزینه 4" in contents
    assert "بدنه پاسخ" in contents
