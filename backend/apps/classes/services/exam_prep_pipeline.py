"""Simple production coordinator for exam-preparation PDFs.

The pipeline renders one PDF page at a time, carries the PDF's own text layer as
supporting evidence, extracts one ``PageExtraction`` for that page, and
deterministically assembles records by ``(scope_key, question_number)``.
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
from apps.classes.services.exam_prep_page_records import (
    AssemblyIssue,
    PageAssemblyResult,
    PageExtraction,
    assemble_page_extractions,
    build_page_first_audit,
    render_page_first_transcript,
)
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
    model: str


ProgressCallback = Callable[[int, int], None]
CancelCheck = Callable[[], bool]


@dataclass(frozen=True, slots=True)
class ExamPrepPdfSource:
    """Validated PDF metadata with a lazy physical-page renderer."""

    data: bytes
    page_count: int
    scale: float
    max_image_bytes: int
    native_text_pages: tuple[str, ...]

    def __iter__(self) -> Iterator[RenderedExamPage]:
        return self.iter_pages()

    def iter_pages(self) -> Iterator[RenderedExamPage]:
        """Yield one page image and release it before rendering the next page."""

        import pypdfium2 as pdfium

        document = pdfium.PdfDocument(self.data)
        try:
            for index in range(self.page_count):
                page = document[index]
                image = None
                try:
                    image = page.render(scale=self.scale).to_pil()
                    png = _encode_png(image, max_bytes=self.max_image_bytes)
                except Exception as exc:
                    raise ExamPrepPdfError(
                        f"رندر صفحهٔ {index + 1} ناموفق بود."
                    ) from exc
                finally:
                    if image is not None:
                        image.close()
                    page.close()
                yield RenderedExamPage(
                    page_number=index + 1,
                    image=png,
                    mime_type="image/png",
                    native_text=(
                        self.native_text_pages[index]
                        if index < len(self.native_text_pages)
                        else ""
                    ),
                )
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


def _extract_native_text(page: Any, *, page_number: int) -> str:
    """Read a digital text layer without making the PDF depend on it."""

    try:
        try:
            value = page.extract_text(extraction_mode="layout")
        except TypeError:
            value = page.extract_text()
    except Exception as exc:
        logger.warning(
            "exam_prep.page.native_text_failed pageNumber=%s errorCode=%s",
            page_number,
            type(exc).__name__,
        )
        return ""
    return str(value or "")


def render_exam_prep_pdf(data: bytes) -> ExamPrepPdfSource:
    """Validate a PDF and return native text plus a lazy image renderer."""

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

    native_text_pages = tuple(
        _extract_native_text(page, page_number=index)
        for index, page in enumerate(reader.pages, start=1)
    )
    generic_dpi = max(72, int(getattr(settings, "PDF_RENDER_DPI", 150)))
    # Dense exam pages contain small Persian text. Keep the simple full-page
    # model, but use an accuracy-first render unless production overrides it.
    dpi = _positive_int_env("EXAM_PREP_RENDER_DPI", max(200, generic_dpi))
    generic_max_mb = max(
        1,
        int(getattr(settings, "PDF_MAX_IMAGE_BYTES_MB", 3)),
    )
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
    )


def _page_iterator(
    source: ExamPrepPdfSource | Sequence[RenderedExamPage],
) -> tuple[int, Iterator[RenderedExamPage]]:
    """Normalize the production lazy source and small in-memory test fixtures."""

    if isinstance(source, ExamPrepPdfSource):
        return source.page_count, source.iter_pages()
    return len(source), iter(source)


def _page_extraction_attempts() -> int:
    try:
        return max(
            1,
            min(
                3,
                int(os.getenv("EXAM_PREP_PAGE_EXTRACTION_ATTEMPTS", "2")),
            ),
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
    """Render, extract, quality-check, and assemble one PDF."""

    source = render_exam_prep_pdf(data)
    selected_model = select_exam_prep_page_model(model)
    extracted: list[PageExtraction] = []
    failed_page_numbers: list[int] = []
    total, pages = _page_iterator(source)
    attempts = _page_extraction_attempts()

    for index, page in enumerate(pages, start=1):
        if should_cancel is not None and should_cancel():
            raise ExamPrepPipelineCancelled("Cancellation requested.")

        page_result: PageExtraction | None = None
        for attempt in range(1, attempts + 1):
            try:
                page_result = extract_exam_prep_page(
                    page,
                    model=selected_model,
                    scope_hint=scope_hint,
                )
                break
            except (StructuredOutputError, ExtractedPageNumberMismatch) as exc:
                error_kind, locations = _safe_error_metadata(exc)
                logger.warning(
                    "exam_prep.page.invalid pageNumber=%s attempt=%s "
                    "maxAttempts=%s errorKind=%s locations=%s",
                    page.page_number,
                    attempt,
                    attempts,
                    error_kind,
                    locations,
                )
                if should_cancel is not None and should_cancel():
                    raise ExamPrepPipelineCancelled(
                        "Cancellation requested."
                    ) from exc

        if page_result is None:
            failed_page_numbers.append(page.page_number)
            logger.error(
                "exam_prep.page.skipped pageNumber=%s attempts=%s",
                page.page_number,
                attempts,
            )
        else:
            extracted.append(page_result)

        if on_page_complete is not None:
            on_page_complete(index, total)

    if should_cancel is not None and should_cancel():
        raise ExamPrepPipelineCancelled("Cancellation requested.")

    assembled: PageAssemblyResult = assemble_page_extractions(
        extracted,
        title=title,
    )
    if assembled.question_count < 1:
        failed_suffix = (
            f" Failed pages: {failed_page_numbers}"
            if failed_page_numbers
            else ""
        )
        raise NoExamQuestionsFound(
            f"هیچ سؤال شماره‌داری در PDF تشخیص داده نشد.{failed_suffix}"
        )

    audit = build_page_first_audit(
        assembled,
        failed_page_numbers=failed_page_numbers,
    )
    transcript = render_page_first_transcript(
        assembled,
        failed_page_numbers=failed_page_numbers,
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
        model=selected_model,
    )
