"""Network-free contracts for the source-first OCR4 path."""
from __future__ import annotations

from io import BytesIO
import json
from types import SimpleNamespace

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from pypdf import PdfWriter

from apps.classes.services.exam_prep_source_first import (
    OCR4Chunk,
    OCR4ChunkResult,
    SourceFirstConfigurationError,
    SourceFirstCoverageError,
    SourceFirstOCRConfig,
    _request_chunk,
    build_segment_blocks,
    merge_chunk_results,
    plan_pdf_chunks,
    write_source_first_bundle,
)
import apps.classes.services.exam_prep_source_first as source_first
from apps.classes.services.exam_prep_v4_avalai_ocr import (
    AvalAIOCRPage,
    AvalAIOCRResult,
)


def _pdf(path, page_count: int) -> None:
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=612, height=792)
    with path.open("wb") as handle:
        writer.write(handle)


def _chunk_response(page_count: int, *, status: int = 200):
    pages = []
    for index in range(page_count):
        pages.append(
            {
                "index": index,
                "markdown": f"{index + 1}- متن آزمون",
                "dimensions": {"width": 1000, "height": 1400, "dpi": 87},
                "blocks": [
                    {
                        "type": "text",
                        "top_left_x": 50,
                        "top_left_y": 100,
                        "bottom_right_x": 900,
                        "bottom_right_y": 180,
                        "content": f"{index + 1}- متن آزمون",
                    }
                ],
            }
        )
    payload = {"model": "mistral-ocr-4-0", "pages": pages}
    return SimpleNamespace(
        status_code=status,
        headers={"x-request-id": "test-request"},
        content=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
    )


def _parsed(chunk, root):
    pages = tuple(
        AvalAIOCRPage(
            index=int(page["index"]),
            markdown=str(page.get("markdown") or ""),
            width=1000,
            height=1400,
            dpi=87,
            blocks=(),
            images=(),
            page_confidence=None,
        )
        for page in root["pages"]
    )
    return AvalAIOCRResult(
        model="mistral-ocr-4-0",
        request_id="test-request",
        pages=pages,
        document_annotation=None,
        usage_pages_processed=len(pages),
        usage_document_bytes=None,
        issues=(),
        latency_ms=1,
    )


def test_plan_55_pages_is_two_contiguous_chunks(tmp_path):
    path = tmp_path / "exam.pdf"
    _pdf(path, 55)
    chunks = plan_pdf_chunks(path)
    assert [len(chunk.physical_pages) for chunk in chunks] == [30, 25]
    assert chunks[0].physical_pages == tuple(range(1, 31))
    assert chunks[1].physical_pages == tuple(range(31, 56))


def test_planner_fails_before_network_when_single_page_exceeds_cap(tmp_path):
    path = tmp_path / "exam.pdf"
    _pdf(path, 1)
    with pytest.raises(SourceFirstConfigurationError, match="alone"):
        plan_pdf_chunks(path, max_chunk_bytes=10)


def test_transient_502_retries_but_bad_request_does_not():
    chunk = OCR4Chunk(index=1, physical_pages=(1,), data=b"pdf", sha256="sha")
    config = SourceFirstOCRConfig(max_attempts=2, retry_backoff_seconds=0, retry_jitter_seconds=0)
    calls = []

    def transport(_endpoint, **_kwargs):
        calls.append(1)
        return _chunk_response(1, status=502 if len(calls) == 1 else 200)

    result = _request_chunk(
        chunk,
        config=config,
        api_key="key",
        transport=transport,
    )
    assert result.retry_count == 1
    assert len(calls) == 2

    bad_calls = []

    def bad_transport(_endpoint, **_kwargs):
        bad_calls.append(1)
        return _chunk_response(1, status=400)

    with pytest.raises(Exception) as error:
        _request_chunk(
            chunk,
            config=config,
            api_key="key",
            transport=bad_transport,
        )
    assert getattr(error.value, "retryable", False) is False
    assert len(bad_calls) == 1


def test_conflict_status_is_not_retried_as_a_paid_duplicate():
    chunk = OCR4Chunk(index=1, physical_pages=(1,), data=b"pdf", sha256="sha")
    calls = []

    def transport(_endpoint, **_kwargs):
        calls.append(1)
        return _chunk_response(1, status=409)

    with pytest.raises(Exception) as error:
        _request_chunk(
            chunk,
            config=SourceFirstOCRConfig(max_attempts=3),
            api_key="key",
            transport=transport,
        )
    assert getattr(error.value, "retryable", False) is False
    assert len(calls) == 1


def test_merge_rejects_duplicate_or_missing_physical_pages():
    root = {"pages": [{"index": 0, "markdown": "x"}]}
    chunk = SimpleNamespace(index=1, physical_pages=(1,), data=b"x", sha256="x")
    parsed = _parsed(chunk, root)
    result = OCR4ChunkResult(chunk=chunk, root=root, parsed=parsed)
    merged = merge_chunk_results(source_sha256="source", page_count=1, chunk_results=[result])
    assert merged.pages[0]["sourcePhysicalPage"] == 1
    with pytest.raises(SourceFirstCoverageError):
        merge_chunk_results(source_sha256="source", page_count=2, chunk_results=[result])


def test_segment_blocks_use_confirmed_role_and_normalized_geometry():
    segment = SimpleNamespace(
        role="questions",
        start_page=1,
        end_page=1,
        metadata={"pageNumbers": [1]},
    )
    page = SimpleNamespace(page_number=1)
    analysis = {
        "pages": [
            {
                "originalPageNumber": 1,
                "regions": [
                    {
                        "kind": "question",
                        "questionNumber": 7,
                        "bbox": [0.1, 0.2, 0.9, 0.8],
                    },
                    {
                        "kind": "solution",
                        "questionNumber": 7,
                        "bbox": [0.1, 0.2, 0.9, 0.8],
                    },
                ],
            }
        ]
    }
    output = build_segment_blocks(analysis, segment=segment, pages=[page])
    assert len(output["blocks"]) == 1
    assert output["blocks"][0]["kind"] == "question"
    assert output["blocks"][0]["fragments"][0]["pageNumber"] == 1


def test_segment_blocks_remap_v4_oriented_page_bbox():
    segment = SimpleNamespace(
        role="questions",
        start_page=1,
        end_page=1,
        metadata={"pageNumbers": [1]},
    )
    page = SimpleNamespace(page_number=1, orientation=90)
    analysis = {
        "pages": [
            {
                "originalPageNumber": 1,
                "regions": [
                    {
                        "kind": "question",
                        "questionNumber": 1,
                        "bbox": [0.1, 0.2, 0.4, 0.6],
                    }
                ],
            }
        ]
    }
    output = build_segment_blocks(analysis, segment=segment, pages=[page])
    assert output["blocks"][0]["fragments"][0]["x0"] == pytest.approx(0.4)
    assert output["blocks"][0]["fragments"][0]["y0"] == pytest.approx(0.1)
    assert output["blocks"][0]["fragments"][0]["x1"] == pytest.approx(0.8)
    assert output["blocks"][0]["fragments"][0]["y1"] == pytest.approx(0.4)


def test_segment_blocks_fail_closed_on_partial_or_recovered_heading():
    segment = SimpleNamespace(
        role="questions",
        start_page=1,
        end_page=2,
        metadata={"pageNumbers": [1, 2]},
    )
    pages = [
        SimpleNamespace(page_number=1, orientation=0),
        SimpleNamespace(page_number=2, orientation=0),
    ]
    partial = {
        "pages": [
            {
                "originalPageNumber": 1,
                "regions": [
                    {
                        "kind": "question",
                        "questionNumber": 1,
                        "bbox": [0.1, 0.1, 0.9, 0.4],
                    }
                ],
            },
            {"originalPageNumber": 2, "regions": []},
        ]
    }
    assert build_segment_blocks(partial, segment=segment, pages=pages) == {"blocks": []}

    recovered = {
        "pages": [
            {
                "originalPageNumber": 1,
                "regions": [
                    {
                        "kind": "question",
                        "questionNumber": 1,
                        "numberRecoveredFromSequence": True,
                        "bbox": [0.1, 0.1, 0.9, 0.4],
                    }
                ],
            }
        ]
    }
    one_page_segment = SimpleNamespace(
        role="questions", start_page=1, end_page=1, metadata={"pageNumbers": [1]}
    )
    assert build_segment_blocks(
        recovered, segment=one_page_segment, pages=pages[:1]
    ) == {"blocks": []}


def test_adapter_caches_one_document_ocr_and_delegates_semantics(tmp_path, monkeypatch):
    pdf_path = tmp_path / "source.pdf"
    _pdf(pdf_path, 1)
    raw = {
        "model": "mistral-ocr-4-0",
        "pages": [
            {
                "index": 0,
                "markdown": "1- text",
                "dimensions": {"width": 1000, "height": 1400},
                "blocks": [
                    {
                        "type": "text",
                        "top_left_x": 50,
                        "top_left_y": 100,
                        "bottom_right_x": 900,
                        "bottom_right_y": 180,
                        "content": "1- text",
                    }
                ],
            }
        ],
    }
    chunk = OCR4Chunk(1, (1,), b"pdf", "chunk")
    parsed = _parsed(chunk, raw)
    document_result = merge_chunk_results(
        source_sha256="source",
        page_count=1,
        chunk_results=[OCR4ChunkResult(chunk=chunk, root=raw, parsed=parsed)],
    )
    calls = []

    def fake_fetch(*_args, **_kwargs):
        calls.append(1)
        return document_result

    monkeypatch.setattr(source_first, "fetch_document_ocr4", fake_fetch)
    fallback = SimpleNamespace(
        provider_calls=3,
        detect_segment_blocks=lambda **_kwargs: {"blocks": []},
        extract_questions_batch=lambda **_kwargs: {"questions": []},
    )
    adapter = source_first.MistralSourceFirstAdapter(
        fallback=fallback,
        config=SourceFirstOCRConfig(max_attempts=1),
        api_key="key",
    )
    document = SimpleNamespace(
        id=1,
        classification_revision=1,
        source_map_fingerprint="fingerprint",
        source_file=pdf_path,
        original_name="source.pdf",
    )
    segment = SimpleNamespace(
        role="questions",
        start_page=1,
        end_page=1,
        metadata={"pageNumbers": [1]},
    )
    page = SimpleNamespace(page_number=1, orientation=0)
    first = adapter.detect_segment_blocks(document=document, segment=segment, pages=[page], images=[])
    second = adapter.detect_segment_blocks(document=document, segment=segment, pages=[page], images=[])
    assert first == second
    assert len(calls) == 1
    assert adapter.provider_calls == 4
    assert adapter.stats.ocr_calls == 1


def test_source_first_command_dry_run_is_network_free_for_attached_shape(tmp_path):
    pdf_path = tmp_path / "exam.pdf"
    _pdf(pdf_path, 55)
    output = tmp_path / "plan"
    call_command(
        "extract_exam_prep_source_first",
        pdf=str(pdf_path),
        output_dir=str(output),
        dry_run=True,
    )
    plan = json.loads((output / "plan.safe.json").read_text(encoding="utf-8"))
    assert plan["pageCount"] == 55
    assert plan["chunkPageCounts"] == [30, 25]
    assert plan["plannedCostUnitUpperBound"] == "0.220"


def test_source_first_resume_requires_its_checkpoint(tmp_path, monkeypatch):
    pdf_path = tmp_path / "exam.pdf"
    _pdf(pdf_path, 1)
    output = tmp_path / "resume"
    output.mkdir()
    (output / "unrelated.raw.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("AVALAI_API_KEY", "test-key")
    with pytest.raises(CommandError, match="checkpoint.json"):
        call_command(
            "extract_exam_prep_source_first",
            pdf=str(pdf_path),
            output_dir=str(output),
            resume=True,
            allow_private_transmission=True,
        )


def test_safe_manifest_excludes_ocr_text_and_marks_source_authority(tmp_path):
    pdf_path = tmp_path / "exam.pdf"
    _pdf(pdf_path, 1)
    raw = {
        "model": "mistral-ocr-4-0",
        "pages": [
            {
                "index": 0,
                "markdown": "متن خصوصی سؤال",
                "dimensions": {"width": 1000, "height": 1400},
                "blocks": [{"type": "text", "content": "متن"}],
                "confidence_scores": {
                    "word_confidence_scores": [{"text": "متن", "confidence": 0.99}]
                },
            }
        ],
    }
    chunk = OCR4Chunk(1, (1,), b"pdf", "chunk")
    result = merge_chunk_results(
        source_sha256="source",
        page_count=1,
        chunk_results=[OCR4ChunkResult(chunk=chunk, root=raw, parsed=_parsed(chunk, raw))],
    )
    analysis = {
        "pages": [
            {
                "originalPageNumber": 1,
                "pageRole": "question",
                "issues": [],
                "regions": [
                    {
                        "kind": "question",
                        "questionNumber": 1,
                        "bbox": [0.1, 0.1, 0.9, 0.8],
                        "text": "متن خصوصی سؤال",
                        "issues": [],
                        "visuals": [],
                    }
                ],
            }
        ],
        "totals": {"questionRegions": 1, "solutionRegions": 0},
    }
    write_source_first_bundle(
        pdf_path=pdf_path,
        result=result,
        analysis=analysis,
        output_dir=tmp_path / "bundle",
        write_page_images=False,
    )
    safe = json.loads((tmp_path / "bundle" / "manifest.safe.json").read_text())
    private = json.loads((tmp_path / "bundle" / "manifest.json").read_text())
    assert safe["acceptancePassed"] is True
    assert safe["providerImageBlocksAreNotComplete"] is True
    assert "ocrText" not in json.dumps(safe, ensure_ascii=False)
    assert "متن خصوصی سؤال" in json.dumps(private, ensure_ascii=False)
