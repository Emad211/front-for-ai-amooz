import json
from types import SimpleNamespace

import pytest

from apps.classes.services import exam_prep_inventory_pipeline as pipeline
from apps.classes.services.schemas import (
    ExamPrepAnswerInventoryOutput,
    ExamPrepPageManifestOutput,
    ExamPrepQuestionInventoryOutput,
)


pytestmark = pytest.mark.unit


def test_single_block_media_is_sent_to_both_inventory_phases():
    blocks = [{"page_number": 1, "block_order": 0, "content": "سؤال و پاسخ"}]
    manifest = {
        1: {
            "page_number": 1,
            "section_type": "questions",
            "confidence": 0.99,
        }
    }

    assert pipeline._candidate_blocks(blocks, manifest, kind="questions") == blocks
    assert pipeline._candidate_blocks(blocks, manifest, kind="answers") == blocks


def _fake_call(*, schema, **kwargs):
    if schema is ExamPrepPageManifestOutput:
        return schema.model_validate({
            "title": "آزمون زیست",
            "pages": [
                {
                    "page_number": 1,
                    "section_type": "answers",
                    "section_key": "زیست",
                    "answer_numbers": ["77", "78"],
                    "confidence": 0.99,
                },
                {
                    "page_number": 2,
                    "section_type": "questions",
                    "section_key": "زیست",
                    "question_numbers": ["78"],
                    "confidence": 0.99,
                },
            ],
        })
    if schema is ExamPrepQuestionInventoryOutput:
        return schema.model_validate({
            "questions": [{
                "source_question_number": "۷۸",
                "section_key": "زیست",
                "source_pages": [2],
                "block_order": 1,
                "question_text_markdown": "کدام گزینه درست است؟",
                "options": [
                    {"label": "الف", "text_markdown": "گزینه اول"},
                    {"label": "ب", "text_markdown": "گزینه دوم"},
                ],
                "confidence": 0.98,
            }],
        })
    if schema is ExamPrepAnswerInventoryOutput:
        return schema.model_validate({
            "answers": [
                {
                    "source_question_number": "77",
                    "section_key": "زیست",
                    "source_pages": [1],
                    "block_order": 0,
                    "correct_option_label": "الف",
                    "teacher_solution_markdown": "پاسخ خارج از محدوده",
                    "confidence": 0.95,
                },
                {
                    "source_question_number": "78",
                    "section_key": "زیست",
                    "source_pages": [1],
                    "block_order": 0,
                    "correct_option_label": "ب",
                    "teacher_solution_markdown": "",
                    "final_answer_markdown": "گزینه ب",
                    "confidence": 0.99,
                },
            ],
        })
    raise AssertionError(schema)


def test_inventory_pipeline_keeps_source_number_internal_and_drops_out_of_scope(
    monkeypatch,
):
    monkeypatch.setattr(pipeline, "_call", _fake_call)
    monkeypatch.setattr(pipeline, "_select_model", lambda: "test-model")
    monkeypatch.setattr(pipeline, "preferred_provider", lambda: "test-provider")

    projection, artifact, audit, provider, model = pipeline.extract_exam_prep_inventory(
        transcript_markdown=(
            "## صفحه 1\nپاسخ ۷۷ الف\nپاسخ ۷۸ ب\n\n"
            "## صفحه 2\nسؤال ۷۸ کدام گزینه درست است؟"
        )
    )

    questions = projection["exam_prep"]["questions"]
    assert len(questions) == 1
    assert questions[0]["question_id"].startswith("q-")
    assert questions[0]["_source"]["questionNumber"] == "۷۸"
    assert questions[0]["teacher_solution_markdown"] == ""
    assert questions[0]["final_answer_markdown"] == "گزینه ب"
    assert audit["outOfScopeAnswerCount"] == 1
    assert audit["criticalIssueCount"] == 0
    assert audit["status"] == "passed"
    assert artifact["pipeline_version"] == 2
    assert len(artifact["answer_records"]) == 2
    assert sorted(
        record["match_status"] for record in artifact["answer_records"]
    ) == ["matched", "out_of_scope"]
    assert provider == "test-provider"
    assert model == "test-model"


def test_inventory_pipeline_records_failed_answer_chunk_instead_of_silent_empty(
    monkeypatch,
):
    def failing_answer_call(*, schema, **kwargs):
        if schema is ExamPrepAnswerInventoryOutput:
            raise RuntimeError("provider timeout")
        return _fake_call(schema=schema, **kwargs)

    monkeypatch.setattr(pipeline, "_call", failing_answer_call)
    monkeypatch.setattr(pipeline, "_select_model", lambda: "test-model")
    monkeypatch.setattr(pipeline, "preferred_provider", lambda: "test-provider")

    _, artifact, audit, _, _ = pipeline.extract_exam_prep_inventory(
        transcript_markdown="## صفحه 1\nپاسخ ۷۸ ب\n\n## صفحه 2\nسؤال ۷۸ چیست؟"
    )

    assert artifact["failed_chunks"][0]["phase"] == "answers"
    assert audit["status"] == "needs_review"
    assert any(issue["code"] == "failed_chunk" for issue in audit["issues"])


def test_v3_failed_chunk_does_not_persist_provider_error_text(monkeypatch):
    class EmptyUnits:
        def filter(self, **_kwargs):
            return self

        @staticmethod
        def first():
            return None

    def failing_answer_call(*, schema, **kwargs):
        if schema is ExamPrepAnswerInventoryOutput:
            raise RuntimeError("private model output must not be stored")
        result = _fake_call(schema=schema, **kwargs)
        if schema is ExamPrepQuestionInventoryOutput:
            source_block_id = kwargs["blocks"][0]["block_id"]
            return result.model_copy(update={
                "questions": [
                    question.model_copy(
                        update={"source_block_ids": [source_block_id]}
                    )
                    for question in result.questions
                ]
            })
        return result

    monkeypatch.setattr(pipeline, "_call", failing_answer_call)
    monkeypatch.setattr(pipeline, "_select_model", lambda: "test-model")
    monkeypatch.setattr(pipeline, "preferred_provider", lambda: "test-provider")

    _, artifact, _, _, _ = pipeline.extract_exam_prep_inventory(
        transcript_markdown="## صفحه 1\nپاسخ ۷۸ ب\n\n## صفحه 2\nسؤال ۷۸ چیست؟",
        artifact=SimpleNamespace(
            pipeline_version=3,
            revision=1,
            units=EmptyUnits(),
        ),
    )

    assert artifact["failed_chunks"][0]["error"] == "RuntimeError"
