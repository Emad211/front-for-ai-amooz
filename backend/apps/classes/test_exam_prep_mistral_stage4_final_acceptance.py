from __future__ import annotations

from apps.classes.management.commands.replay_exam_prep_mistral_stage4_final import (
    _final_label_audit,
)


def test_final_native_label_audit_requires_exact_labels_and_question_set():
    projection = {
        "exam_prep": {
            "questions": [
                {"source_question_number": "1", "correct_option_label": "2"},
                {"source_question_number": "2", "correct_option_label": "4"},
            ]
        }
    }
    passed = _final_label_audit(projection, authoritative={1: "2", 2: "4"})
    assert passed["passed"] is True
    assert passed["mismatchCount"] == 0
    assert passed["missingLabelCount"] == 0

    failed = _final_label_audit(projection, authoritative={1: "2", 2: "3"})
    assert failed["passed"] is False
    assert failed["mismatchQuestions"] == [2]
