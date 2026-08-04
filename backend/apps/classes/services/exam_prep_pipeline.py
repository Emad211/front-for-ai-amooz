"""Simple production coordinator for exam-preparation PDFs.

The pipeline renders one PDF page at a time, extracts one ``PageExtraction``
for that page, and deterministically assembles records by
``(scope_key, question_number)``. It has no V1/V2/V3/V4 models or intermediate
artifacts.
"""
from __future__ import annotations

from dataclasses import dataclass
import io
from typing import Callable, Iterator, Sequence

from django.conf import settings
from PIL import Image
from pydantic import BaseModel

from apps.classes.services.exam_prep_page_extractor import (
    RenderedExamPage,
    extract_exam_prep_page,
    select_exam_prep_page_model,
)
from apps.classes.services.exam_prep_page_records import (
    AssemblyIssue,
    PageAssemblyResult,
    PageExtraction,
    assemble_page_extractions,
)


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
                        f'رندر صفحهٔ {index + 1} ناموفق بود.'
                    ) from exc
                finally:
                    if image is not None:
                        image.close()
                    page.close()
                yield RenderedExamPage(
                    page_number=index + 1,
                    image=png,
                    mime_type='image/png',
                )
        finally:
            document.close()


def _encode_png(image: Image.Image, *, max_bytes: int) -> bytes:
    rendered = image.convert('RGB')
    try:
        encoded = b''
        for _ in range(6):
            buffer = io.BytesIO()
            rendered.save(buffer, format='PNG', optimize=True)
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


def render_exam_prep_pdf(data: bytes) -> ExamPrepPdfSource:
    """Validate a PDF and return a lazy page renderer in physical order."""

    from pypdf import PdfReader

    if not data or not data.lstrip().startswith(b'%PDF'):
        raise ExamPrepPdfError('فایل ارسالی یک PDF معتبر نیست.')

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            try:
                if reader.decrypt('') == 0:
                    raise ExamPrepPdfError(
                        'PDF رمزگذاری‌شده است؛ نسخهٔ بدون رمز را بارگذاری کنید.'
                    )
            except ExamPrepPdfError:
                raise
            except Exception as exc:
                raise ExamPrepPdfError(
                    'PDF رمزگذاری‌شده است؛ نسخهٔ بدون رمز را بارگذاری کنید.'
                ) from exc
        page_count = len(reader.pages)
    except ExamPrepPdfError:
        raise
    except Exception as exc:
        raise ExamPrepPdfError('خواندن PDF ناموفق بود.') from exc

    if page_count < 1:
        raise ExamPrepPdfError('PDF هیچ صفحه‌ای ندارد.')
    max_pages = max(1, int(getattr(settings, 'PDF_MAX_PAGES', 200)))
    if page_count > max_pages:
        raise ExamPrepPdfError(
            f'تعداد صفحات PDF از حداکثر مجاز {max_pages} بیشتر است.'
        )

    dpi = max(72, int(getattr(settings, 'PDF_RENDER_DPI', 150)))
    max_image_bytes = max(
        1,
        int(getattr(settings, 'PDF_MAX_IMAGE_BYTES_MB', 3)),
    ) * 1024 * 1024
    return ExamPrepPdfSource(
        data=data,
        page_count=page_count,
        scale=dpi / 72.0,
        max_image_bytes=max_image_bytes,
    )


def _page_iterator(
    source: ExamPrepPdfSource | Sequence[RenderedExamPage],
) -> tuple[int, Iterator[RenderedExamPage]]:
    """Normalize the production lazy source and small in-memory test fixtures."""

    if isinstance(source, ExamPrepPdfSource):
        return source.page_count, source.iter_pages()
    return len(source), iter(source)


def run_exam_prep_pdf_pipeline(
    *,
    data: bytes,
    title: str,
    model: str | None = None,
    scope_hint: str = 'default',
    on_page_complete: ProgressCallback | None = None,
    should_cancel: CancelCheck | None = None,
) -> ExamPrepPipelineResult:
    """Render, extract, and assemble one PDF without legacy intermediates."""

    source = render_exam_prep_pdf(data)
    selected_model = select_exam_prep_page_model(model)
    extracted: list[PageExtraction] = []
    total, pages = _page_iterator(source)

    for index, page in enumerate(pages, start=1):
        if should_cancel is not None and should_cancel():
            raise ExamPrepPipelineCancelled('Cancellation requested.')
        extracted.append(
            extract_exam_prep_page(
                page,
                model=selected_model,
                scope_hint=scope_hint,
            )
        )
        if on_page_complete is not None:
            on_page_complete(index, total)

    if should_cancel is not None and should_cancel():
        raise ExamPrepPipelineCancelled('Cancellation requested.')

    assembled: PageAssemblyResult = assemble_page_extractions(
        extracted,
        title=title,
    )
    if assembled.question_count < 1:
        raise NoExamQuestionsFound(
            'هیچ سؤال شماره‌داری در PDF تشخیص داده نشد.'
        )

    return ExamPrepPipelineResult(
        projection=assembled.projection,
        issues=assembled.issues,
        page_count=total,
        question_count=assembled.question_count,
        questions_needing_review=assembled.questions_needing_review,
        model=selected_model,
    )
