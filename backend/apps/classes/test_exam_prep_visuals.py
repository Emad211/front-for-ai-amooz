import base64
import io
from types import SimpleNamespace

import pytest
from model_bakery import baker
from PIL import Image

from apps.classes.models import (
    ClassCreationSession,
    ExamPrepExtractionArtifact,
    ExamPrepVisualAsset,
)
from apps.classes.services import exam_prep_visuals
from apps.classes.services.schemas import (
    ExamPrepVisualDetectionOutput,
    ExamPrepVisualRegion,
)


def _png(width=200, height=100):
    output = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(output, format="PNG")
    return output.getvalue()


def test_avalai_generation_adapter_uses_documented_multimodal_contract(monkeypatch):
    generated = _png(64, 64)
    image_url = "data:image/png;base64," + base64.b64encode(generated).decode("ascii")
    create = SimpleNamespace()
    calls = []
    create.create = lambda **kwargs: (
        calls.append(kwargs)
        or SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        images=[SimpleNamespace(image_url=SimpleNamespace(url=image_url))]
                    )
                )
            ]
        )
    )
    client = SimpleNamespace(chat=SimpleNamespace(completions=create))
    monkeypatch.setattr(exam_prep_visuals, "_get_gapgpt_client", lambda: client)
    monkeypatch.setattr(exam_prep_visuals, "_generation_model", lambda: "gemini-3.1-flash-lite-image")
    monkeypatch.setattr(exam_prep_visuals, "track_llm_usage", lambda **_kwargs: None)

    data, content_type, model = exam_prep_visuals._generate_candidate(
        visual_spec={"visualType": "geometry", "labels": ["A", "B"]},
    )

    assert data == generated
    assert content_type == "image/png"
    assert model == "gemini-3.1-flash-lite-image"
    assert calls[0]["modalities"] == ["image", "text"]
    assert calls[0]["extra_body"] == {
        "generationConfig": {"imageConfig": {"aspectRatio": "4:3"}}
    }
    assert calls[0]["messages"][0]["content"][0]["type"] == "text"


def test_crop_uses_normalized_bbox_and_rejects_empty_regions():
    cropped = exam_prep_visuals._crop(_png(), [0.25, 0.2, 0.75, 0.8])
    with Image.open(io.BytesIO(cropped)) as image:
        assert 100 <= image.width <= 110
        assert 60 <= image.height <= 70

    with pytest.raises(ValueError):
        exam_prep_visuals._crop(_png(), [0.5, 0.5, 0.5, 0.8])


@pytest.mark.django_db
def test_visual_hint_overrides_false_negative_manifest(monkeypatch):
    teacher = baker.make("accounts.User", role="TEACHER")
    session = baker.make(
        ClassCreationSession,
        teacher=teacher,
        pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
    )
    artifact = ExamPrepExtractionArtifact.objects.create(
        session=session,
        source_blocks=[{
            "sourceKind": "pdf_page",
            "pageNumber": 1,
            "storageName": "private/page-1.png",
            "contentType": "image/png",
        }],
        page_manifest={"pages": [{
            "page_number": 1,
            "section_type": "questions",
            "has_visuals": False,
        }]},
        question_records=[{
            "question_id": "q-78",
            "source_question_number": "78",
            "section_key": "زیست",
            "source_pages": [1],
            "visual_hints": ["نمودار"],
        }],
    )
    detection_calls = []
    monkeypatch.setattr(exam_prep_visuals, "_read_private", lambda _name: _png())
    monkeypatch.setattr(
        exam_prep_visuals,
        "_detect_visuals",
        lambda **kwargs: (
            detection_calls.append(kwargs)
            or ExamPrepVisualDetectionOutput(
                visuals=[
                    ExamPrepVisualRegion(
                        question_number="۷۸",
                        section_key="زیست",
                        role="question",
                        bbox=[0.1, 0.1, 0.9, 0.9],
                        alt_text="نمودار سؤال",
                        visual_type="chart",
                        specification={"labels": ["A"]},
                    )
                ]
            )
        ),
    )
    monkeypatch.setattr(exam_prep_visuals, "image_generation_enabled", lambda: False)
    projection = {
        "exam_prep": {
            "title": "آزمون",
            "questions": [{"question_id": "q-78", "visuals": []}],
        }
    }

    result, issues = exam_prep_visuals.process_exam_prep_visuals(
        artifact=artifact,
        projection=projection,
        model="vision-model",
    )

    asset = ExamPrepVisualAsset.objects.get(artifact=artifact)
    try:
        assert detection_calls
        assert issues == []
        assert result["exam_prep"]["questions"][0]["visuals"][0]["id"] == asset.id
        assert asset.selected_variant == ExamPrepVisualAsset.SelectedVariant.SOURCE
    finally:
        asset.source_file.delete(save=False)


@pytest.mark.django_db
def test_question_and_solution_visuals_with_same_order_remain_distinct(monkeypatch):
    session = baker.make(
        ClassCreationSession,
        pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
    )
    artifact = ExamPrepExtractionArtifact.objects.create(
        session=session,
        source_blocks=[{
            "sourceKind": "pdf_page",
            "pageNumber": 1,
            "storageName": "private/page-1.png",
            "contentType": "image/png",
            "sha256": "a" * 64,
        }],
        page_manifest={"pages": [{"page_number": 1, "has_visuals": True}]},
        question_records=[{
            "question_id": "q-78",
            "source_question_number": "78",
            "section_key": "زیست",
            "source_pages": [1],
        }],
    )
    monkeypatch.setattr(exam_prep_visuals, "_read_private", lambda _name: _png())
    monkeypatch.setattr(
        exam_prep_visuals,
        "_detect_visuals",
        lambda **_kwargs: ExamPrepVisualDetectionOutput(
            visuals=[
                ExamPrepVisualRegion(
                    question_number="78",
                    section_key="زیست",
                    role=role,
                    order=0,
                    bbox=bbox,
                    alt_text=role,
                    visual_type="diagram",
                )
                for role, bbox in (
                    ("question", [0.05, 0.05, 0.45, 0.9]),
                    ("solution", [0.55, 0.05, 0.95, 0.9]),
                )
            ]
        ),
    )
    monkeypatch.setattr(exam_prep_visuals, "image_generation_enabled", lambda: False)
    projection = {
        "exam_prep": {
            "title": "آزمون",
            "questions": [{"question_id": "q-78", "visuals": []}],
        }
    }

    result, issues = exam_prep_visuals.process_exam_prep_visuals(
        artifact=artifact,
        projection=projection,
        model="vision-model",
    )

    try:
        assets = list(artifact.visual_assets.order_by("role"))
        assert issues == []
        assert len(assets) == 2
        assert len({asset.asset_key for asset in assets}) == 2
        assert len(result["exam_prep"]["questions"][0]["visuals"]) == 2
    finally:
        for asset in artifact.visual_assets.all():
            asset.source_file.delete(save=False)
