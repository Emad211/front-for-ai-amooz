"""Simple production coordinator for exam-preparation PDFs.

Each model call remains local: one page/column, or one suspicious assembled
question with at most one question crop and one answer crop. No whole-PDF prompt
exists.
"""
from __future__ import annotations

from dataclasses import dataclass
import io
import logging
import os
from typing import Any, Callable, Iterator, Sequence

from django.conf import settings
from PIL import Image
from pydantic import BaseModel, Field

from apps.classes.services.exam_prep_page_extractor import (
    ExtractedPageNumberMismatch,
    RenderedExamPage,
    extract_exam_prep_page,
    select_exam_prep_page_model,
)
from apps.classes.services.exam_prep_page_output import (
    build_strict_page_first_audit,
    render_strict_page_first_transcript,
)
from apps.classes.services.exam_prep_page_records import (
    AssemblyIssue,
    PageAssemblyResult,
    PageExtraction,
    assemble_page_extractions,
)
from apps.classes.services.exam_prep_page_regions import last_record_number
from apps.classes.services.exam_prep_page_source import attach_source_regions
from apps.classes.services.exam_prep_question_targeted_verifier import (
    targeted_source_page_numbers,
    verify_suspicious_questions,
)
from apps.classes.services.exam_prep_question_verifier import rebuild_assembly_quality
from apps.commons.structured_llm import StructuredOutputError


logger = logging.getLogger("apps.classes.exam_prep")


class ExamPrepPdfError(RuntimeError):
    """Raised when the uploaded PDF cannot be rendered safely."""


class ExamPrepPipelineCancelled(RuntimeError):
    """Raised at a page boundary when the teacher requested cancellation."""


class NoExamQuestionsFound(RuntimeError):
    """Raised when no numbered question record was found in the PDF."""


class ExamPrepPipelineResult(BaseModel):
    projection: dict
    issues: list[AssemblyIssue]
    page_count: int
    question_count: int
    questions_needing_review: int
    matched_answer_count: int = 0
    orphan_answer_count: int = 0
    question_number_gaps: dict[str, list[int]] = Field(default_factory=dict)
    failed_page_numbers: list[int] = Field(default_factory=list)
    publication_ready: bool = False
    transcript_markdown: str = ""
    extraction_audit: dict[str, Any] = Field(default_factory=dict)
    targeted_repair_stats: dict[str, int] = Field(default_factory=dict)
    verification_stats: dict[str, int] = Field(default_factory=dict)
    model: str


ProgressCallback = Callable[[int, int], None]
CancelCheck = Callable[[], bool]


@dataclass(frozen=True, slots=True)
class ExamPrepPdfSource:
    data: bytes
    page_count: int
    scale: float
    max_image_bytes: int
    native_text_pages: tuple[str, ...]
    right_column_text_pages: tuple[str, ...]
    left_column_text_pages: tuple[str, ...]

    def __iter__(self) -> Iterator[RenderedExamPage]:
        return self.iter_pages()

    def _text(self, values: tuple[str, ...], index: int) -> str:
        return values[index] if 0 <= index < len(values) else ""

    def _build_page(self, document: Any, index: int) -> RenderedExamPage:
        page = document[index]
        image = None
        try:
            image = page.render(scale=self.scale).to_pil()
            png = _encode_png(image, max_bytes=self.max_image_bytes)
        except Exception as exc:
            raise ExamPrepPdfError(f"رندر صفحهٔ {index + 1} ناموفق بود.") from exc
        finally:
            if image is not None:
                image.close()
            page.close()
        return RenderedExamPage(
            page_number=index + 1,
            image=png,
            mime_type="image/png",
            native_text=self._text(self.native_text_pages, index),
            previous_native_text=self._text(self.native_text_pages, index - 1),
            next_native_text=self._text(self.native_text_pages, index + 1),
            right_column_native_text=self._text(self.right_column_text_pages, index),
            left_column_native_text=self._text(self.left_column_text_pages, index),
        )

    def iter_pages(self) -> Iterator[RenderedExamPage]:
        import pypdfium2 as pdfium

        document = pdfium.PdfDocument(self.data)
        try:
            for index in range(self.page_count):
                yield self._build_page(document, index)
        finally:
            document.close()

    def render_selected_pages(self, page_numbers: set[int]) -> dict[int, RenderedExamPage]:
        """Re-render each unique source page once for targeted crop verification."""

        import pypdfium2 as pdfium

        selected = sorted(
            number
            for number in {int(value) for value in page_numbers}
            if 1 <= number <= self.page_count
        )
        if not selected:
            return {}
        document = pdfium.PdfDocument(self.data)
        try:
            return {
                number: self._build_page(document, number - 1)
                for number in selected
            }
        finally:
            document.close()


def _positive_int_env(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def _encode_png(image: Image.Image, *, max_bytes: int) -> bytes:
    rendered = image.convert("RGB")
    try:
        encoded = b""
        for _ in range(6):
            buffer = io.BytesIO()
            rendered.save(buffer, format="PNG", optimize=True)
            encoded = buffer.getvalue()
            if len(encoded) <= max_bytes or min(rendered.size) <= 320:
                return encoded
            width, height = rendered.size
            resized = rendered.resize(
                (max(320, int(width * 0.75)), max(320, int(height * 0.75))),
                Image.Resampling.LANCZOS,
            )
            rendered.close()
            rendered = resized
        return encoded
    finally:
        rendered.close()


def _extract_text(page: Any, *, layout: bool = True) -> str:
    try:
        if layout:
            try:
                return str(page.extract_text(layout=True) or "")
            except TypeError:
                pass
        return str(page.extract_text() or "")
    except Exception:
        return ""


def _extract_native_text_bundle(
    data: bytes,
    *,
    fallback_pages: Sequence[Any],
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Extract full/right/left text; failure falls back to pypdf full text."""

    try:
        import pdfplumber

        full_pages: list[str] = []
        right_pages: list[str] = []
        left_pages: list[str] = []
        with pdfplumber.open(io.BytesIO(data)) as document:
            for page in document.pages:
                width = float(page.width)
                height = float(page.height)
                full_pages.append(_extract_text(page))
                right_pages.append(
                    _extract_text(page.crop((width / 2, 0, width, height)))
                )
                left_pages.append(
                    _extract_text(page.crop((0, 0, width / 2, height)))
                )
        return tuple(full_pages), tuple(right_pages), tuple(left_pages)
    except Exception as exc:
        logger.warning(
            "exam_prep.native_columns_failed errorCode=%s",
            type(exc).__name__,
        )
        full = tuple(
            _extract_text(page, layout=False)
            for page in fallback_pages
        )
        empty = tuple("" for _ in full)
        return full, empty, empty


def render_exam_prep_pdf(data: bytes) -> ExamPrepPdfSource:
    from pypdf import PdfReader

    if not data or not data.lstrip().startswith(b"%PDF"):
        raise ExamPrepPdfError("فایل ارسالی یک PDF معتبر نیست.")
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            try:
                if reader.decrypt("") == 0:
                    raise ExamPrepPdfError(
                        "PDF رمزگذاری‌شده است؛ نسخهٔ بدون رمز را بارگذاری کنید."
                    )
            except ExamPrepPdfError:
                raise
            except Exception as exc:
                raise ExamPrepPdfError(
                    "PDF رمزگذاری‌شده است؛ نسخهٔ بدون رمز را بارگذاری کنید."
                ) from exc
        page_count = len(reader.pages)
    except ExamPrepPdfError:
        raise
    except Exception as exc:
        raise ExamPrepPdfError("خواندن PDF ناموفق بود.") from exc

    if page_count < 1:
        raise ExamPrepPdfError("PDF هیچ صفحه‌ای ندارد.")
    max_pages = max(1, int(getattr(settings, "PDF_MAX_PAGES", 200)))
    if page_count > max_pages:
        raise ExamPrepPdfError(
            f"تعداد صفحات PDF از حداکثر مجاز {max_pages} بیشتر است."
        )

    native_text_pages, right_text_pages, left_text_pages = _extract_native_text_bundle(
        data,
        fallback_pages=reader.pages,
    )
    generic_dpi = max(72, int(getattr(settings, "PDF_RENDER_DPI", 150)))
    dpi = _positive_int_env("EXAM_PREP_RENDER_DPI", max(200, generic_dpi))
    generic_max_mb = max(1, int(getattr(settings, "PDF_MAX_IMAGE_BYTES_MB", 3)))
    max_image_mb = _positive_int_env(
        "EXAM_PREP_RENDER_MAX_IMAGE_MB",
        max(6, generic_max_mb),
    )
    return ExamPrepPdfSource(
        data=data,
        page_count=page_count,
        scale=dpi / 72.0,
        max_image_bytes=max_image_mb * 1024 * 1024,
        native_text_pages=native_text_pages,
        right_column_text_pages=right_text_pages,
        left_column_text_pages=left_text_pages,
    )


def _page_iterator(
    source: ExamPrepPdfSource | Sequence[RenderedExamPage],
) -> tuple[int, Iterator[RenderedExamPage]]:
    if isinstance(source, ExamPrepPdfSource):
        return source.page_count, source.iter_pages()
    return len(source), iter(source)


def _page_extraction_attempts() -> int:
    try:
        return max(
            1,
            min(3, int(os.getenv("EXAM_PREP_PAGE_EXTRACTION_ATTEMPTS", "2"))),
        )
    except (TypeError, ValueError):
        return 2


def _safe_error_metadata(exc: Exception) -> tuple[str, tuple[str, ...]]:
    return (
        str(getattr(exc, "error_kind", type(exc).__name__))[:80],
        tuple(getattr(exc, "validation_locations", ())[:8]),
    )


def run_exam_prep_pdf_pipeline(
    *,
    data: bytes,
    title: str,
    model: str | None = None,
    scope_hint: str = "default",
    on_page_complete: ProgressCallback | None = None,
    should_cancel: CancelCheck | None = None,
) -> ExamPrepPipelineResult:
    source = render_exam_prep_pdf(data)
    selected_model = select_exam_prep_page_model(model)
    extracted: list[PageExtraction] = []
    failed_page_numbers: list[int] = []
    total, pages = _page_iterator(source)
    attempts = _page_extraction_attempts()
    continuation_hint: int | None = None
    fixture_pages: dict[int, RenderedExamPage] = {}

    for index, page in enumerate(pages, start=1):
        if should_cancel is not None and should_cancel():
            raise ExamPrepPipelineCancelled("Cancellation requested.")
        if not isinstance(source, ExamPrepPdfSource):
            fixture_pages[page.page_number] = page

        page_result: PageExtraction | None = None
        for attempt in range(1, attempts + 1):
            try:
                page_result = extract_exam_prep_page(
                    page,
                    model=selected_model,
                    scope_hint=scope_hint,
                    continuation_hint=continuation_hint,
                )
                break
            except (StructuredOutputError, ExtractedPageNumberMismatch) as exc:
                error_kind, locations = _safe_error_metadata(exc)
                logger.warning(
                    "exam_prep.page.invalid pageNumber=%s attempt=%s maxAttempts=%s errorKind=%s locations=%s",
                    page.page_number,
                    attempt,
                    attempts,
                    error_kind,
                    locations,
                )
                if should_cancel is not None and should_cancel():
                    raise ExamPrepPipelineCancelled("Cancellation requested.") from exc

        if page_result is None:
            failed_page_numbers.append(page.page_number)
            logger.error(
                "exam_prep.page.skipped pageNumber=%s attempts=%s",
                page.page_number,
                attempts,
            )
        else:
            extracted.append(page_result)
            # Never retain a stale hint beyond the immediately continuing block.
            continuation_hint = last_record_number(page_result)

        if on_page_complete is not None:
            on_page_complete(index, total)

    if should_cancel is not None and should_cancel():
        raise ExamPrepPipelineCancelled("Cancellation requested.")

    assembled = assemble_page_extractions(extracted, title=title)
    assembled = attach_source_regions(assembled, pages=extracted)
    assembled = rebuild_assembly_quality(assembled)
    if assembled.question_count < 1:
        failed_suffix = f" Failed pages: {failed_page_numbers}" if failed_page_numbers else ""
        raise NoExamQuestionsFound(
            f"هیچ سؤال شماره‌داری در PDF تشخیص داده نشد.{failed_suffix}"
        )

    needed_pages = targeted_source_page_numbers(assembled)
    if isinstance(source, ExamPrepPdfSource):
        source_page_map = source.render_selected_pages(needed_pages)
    else:
        source_page_map = {
            number: fixture_pages[number]
            for number in needed_pages
            if number in fixture_pages
        }
    assembled, verification_stats = verify_suspicious_questions(
        assembled,
        source_pages_by_number=source_page_map,
        model=selected_model,
    )

    audit = build_strict_page_first_audit(
        assembled,
        failed_page_numbers=failed_page_numbers,
    )
    audit.update(
        {
            "verificationAttempted": verification_stats.get("attempted", 0),
            "verificationSucceeded": verification_stats.get("verified", 0),
            "verificationRepaired": verification_stats.get("repaired", 0),
            "verificationRetried": verification_stats.get("retried", 0),
            "verificationUnresolved": verification_stats.get("unresolved", 0),
            "verificationSkippedByCostCap": verification_stats.get("skipped", 0),
            "visualAttachments": verification_stats.get("visuals_attached", 0),
            "tablesVerified": verification_stats.get("tables_verified", 0),
        }
    )
    transcript = render_strict_page_first_transcript(
        assembled,
        failed_page_numbers=failed_page_numbers,
        targeted_repair_stats=verification_stats,
    )
    logger.info(
        "exam_prep.pipeline.quality_summary questionCount=%s reviewCount=%s verificationAttempted=%s verificationSucceeded=%s verificationRepaired=%s verificationRetried=%s verificationUnresolved=%s verificationSkipped=%s visualAttachments=%s tablesVerified=%s",
        assembled.question_count,
        assembled.questions_needing_review,
        verification_stats.get("attempted", 0),
        verification_stats.get("verified", 0),
        verification_stats.get("repaired", 0),
        verification_stats.get("retried", 0),
        verification_stats.get("unresolved", 0),
        verification_stats.get("skipped", 0),
        verification_stats.get("visuals_attached", 0),
        verification_stats.get("tables_verified", 0),
    )
    return ExamPrepPipelineResult(
        projection=assembled.projection,
        issues=assembled.issues,
        page_count=total,
        question_count=assembled.question_count,
        questions_needing_review=assembled.questions_needing_review,
        matched_answer_count=assembled.matched_answer_count,
        orphan_answer_count=len(assembled.orphan_answers),
        question_number_gaps=assembled.question_number_gaps,
        failed_page_numbers=failed_page_numbers,
        publication_ready=audit.get("status") == "passed",
        transcript_markdown=transcript,
        extraction_audit=audit,
        targeted_repair_stats=verification_stats,
        verification_stats=verification_stats,
        model=selected_model,
    )
