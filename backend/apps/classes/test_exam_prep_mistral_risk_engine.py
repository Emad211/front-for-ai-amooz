from __future__ import annotations

from apps.classes.services.exam_prep_mistral_risk_engine import score_region_risks


def _projection(**question_updates):
    question = {
        "question_id": "default-q-1",
        "source_question_number": "1",
        "question_text_markdown": "کدام گزینه درست است؟",
        "options": [
            {"label": "1", "text_markdown": "الف"},
            {"label": "2", "text_markdown": "ب"},
            {"label": "3", "text_markdown": "ج"},
            {"label": "4", "text_markdown": "د"},
        ],
        "correct_option_label": "2",
        "teacher_solution_markdown": "پاسخ تشریحی خوانا است.",
        "final_answer_markdown": "گزینه 2",
        "issues": [],
        "visuals": [],
    }
    question.update(question_updates)
    return {"exam_prep": {"questions": [question]}}


def _layout(text: str, *, kind: str = "question", issues=None, recovered=False):
    return {
        "pages": [
            {
                "originalPageNumber": 1,
                "regions": [
                    {
                        "kind": kind,
                        "questionNumber": 1,
                        "bbox": [0.50, 0.10, 0.98, 0.60],
                        "text": text,
                        "issues": list(issues or []),
                        "numberRecoveredFromSequence": recovered,
                    }
                ],
            }
        ]
    }


def _only(**kwargs):
    rows = score_region_risks(**kwargs)
    assert len(rows) == 1
    return rows[0]


def test_plain_scientific_prose_stays_clean_without_call():
    row = _only(
        projection=_projection(),
        layout=_layout("در یک سلول، کدام عبارت درباره آنزیم درست است؟"),
    )
    assert row.suspicious is False
    assert row.score < 40
    assert "scientific_terminology" in row.signals


def test_simple_formula_and_units_alone_do_not_force_provider_call():
    row = _only(
        projection=_projection(),
        layout=_layout("اگر v = 3 m/s باشد کدام گزینه درست است؟"),
    )
    assert row.suspicious is False
    assert "formula_math" in row.signals
    assert "digits_units" in row.signals


def test_complex_formula_region_is_suspicious():
    row = _only(
        projection=_projection(),
        layout=_layout(r"f(x)=\\frac{x^2+1}{x-1}, y=\\sqrt{x}, a=3 m/s"),
    )
    assert row.suspicious is True
    assert row.hard_math is True
    assert row.score >= 40


def test_missing_solution_answer_is_strong_risk():
    row = _only(
        projection=_projection(correct_option_label=None, teacher_solution_markdown=""),
        layout=_layout("1- گزینه ؟", kind="solution"),
    )
    assert row.suspicious is True
    assert "missing_invalid_answer" in row.signals
    assert row.score >= 55


def test_recovered_solution_heading_is_risk_even_after_stage2_repair():
    row = _only(
        projection=_projection(),
        layout=_layout("1- گزینه 2\nپاسخ", kind="solution"),
        recovered_solution_targets={1},
    )
    assert row.suspicious is True
    assert "heading_conflict" in row.signals


def test_broken_source_glyph_is_strong_risk():
    row = _only(
        projection=_projection(),
        layout=_layout("عبارت □□ درباره ساختار داده شده است"),
    )
    assert row.suspicious is True
    assert "source_corruption" in row.signals


def test_review_only_visual_is_strong_visual_anomaly():
    row = _only(
        projection=_projection(
            visuals=[
                {
                    "id": "inline-mistral-v1-x",
                    "role": "question",
                    "reviewOnly": True,
                    "sanity": {"status": "needs_review", "issues": ["visual_crop_clipped"]},
                }
            ]
        ),
        layout=_layout("مطابق شکل پاسخ دهید"),
    )
    assert row.suspicious is True
    assert "visual_anomaly" in row.signals
