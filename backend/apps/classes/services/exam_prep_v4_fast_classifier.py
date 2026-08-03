"""Fast multimodal source classifier for Exam Prep V4.

This stage uses low-resolution contact sheets and compact native-text samples.
It classifies page roles only; it never OCRs full questions or extracts answers.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
from dataclasses import dataclass
from typing import Any, Iterable

from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field

from apps.chatbot.services.llm_client import part_from_bytes
from apps.classes.models_v4 import ExamSourceDocument
from apps.classes.services.exam_prep_v4_classification import (
    PersistedClassification,
    persist_classification_result,
)
from apps.commons.llm_prompts import PROMPTS
from apps.commons.models import LLMUsageLog
from apps.commons.structured_llm import generate_structured


PROMPT_VERSION = 'exam-prep-v4-page-classification-v1'
DEFAULT_PAGES_PER_SHEET = 12
DEFAULT_COLUMNS = 3
DEFAULT_THUMBNAIL_WIDTH = 240
DEFAULT_THUMBNAIL_HEIGHT = 320


class FastClassifierConfigurationError(RuntimeError):
    pass


class InvalidContactSheetInput(ValueError):
    pass


class FastClassificationEnvelope(BaseModel):
    """Only the top-level envelope is strict; individual records stay tolerant."""

    model_config = ConfigDict(extra='ignore')
    pages: list[Any] = Field(default_factory=list)


@dataclass(frozen=True, slots=True)
class RenderedPageInput:
    page_number: int
    image: bytes
    mime_type: str = 'image/png'
    native_text_sample: str = ''


@dataclass(frozen=True, slots=True)
class ContactSheet:
    page_numbers: tuple[int, ...]
    image: bytes
    mime_type: str
    sha256: str


@dataclass(frozen=True, slots=True)
class FastClassifierResult:
    model: str
    prompt_version: str
    input_fingerprint: str
    classification: PersistedClassification


def _select_model(explicit_model: str | None = None) -> str:
    model = (
        (explicit_model or '').strip()
        or (os.getenv('EXAM_PREP_V4_CLASSIFICATION_MODEL') or '').strip()
        or (os.getenv('PDF_VISION_MODEL') or '').strip()
    )
    if not model:
        raise FastClassifierConfigurationError(
            'Set EXAM_PREP_V4_CLASSIFICATION_MODEL or PDF_VISION_MODEL.'
        )
    return model.removeprefix('models/')


def _positive_int_env(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def _positive_float_env(name: str, default: float) -> float:
    try:
        return max(1.0, float(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def _open_page_image(page: RenderedPageInput) -> Image.Image:
    if page.page_number < 1:
        raise InvalidContactSheetInput('Page numbers must be one-based.')
    if not page.image:
        raise InvalidContactSheetInput(
            f'Page {page.page_number} does not contain rendered image bytes.'
        )
    try:
        image = Image.open(io.BytesIO(page.image))
        image.load()
        return image.convert('RGB')
    except (UnidentifiedImageError, OSError) as exc:
        raise InvalidContactSheetInput(
            f'Page {page.page_number} is not a readable image.'
        ) from exc


def build_contact_sheets(
    pages: Iterable[RenderedPageInput],
    *,
    pages_per_sheet: int | None = None,
    columns: int = DEFAULT_COLUMNS,
    thumbnail_width: int = DEFAULT_THUMBNAIL_WIDTH,
    thumbnail_height: int = DEFAULT_THUMBNAIL_HEIGHT,
) -> tuple[ContactSheet, ...]:
    """Build bounded JPEG contact sheets with deterministic PAGE labels."""

    ordered = sorted(tuple(pages), key=lambda item: item.page_number)
    if not ordered:
        raise InvalidContactSheetInput('At least one rendered page is required.')
    page_numbers = [page.page_number for page in ordered]
    if len(page_numbers) != len(set(page_numbers)):
        raise InvalidContactSheetInput('Rendered page numbers must be unique.')
    if columns < 1 or thumbnail_width < 64 or thumbnail_height < 64:
        raise InvalidContactSheetInput('Invalid contact-sheet geometry.')

    per_sheet = pages_per_sheet or _positive_int_env(
        'EXAM_PREP_V4_CLASSIFICATION_PAGES_PER_SHEET',
        DEFAULT_PAGES_PER_SHEET,
    )
    if per_sheet < 1:
        raise InvalidContactSheetInput('pages_per_sheet must be positive.')

    font = ImageFont.load_default()
    label_height = 28
    padding = 10
    card_width = thumbnail_width + padding * 2
    card_height = thumbnail_height + label_height + padding * 2
    sheets: list[ContactSheet] = []

    for offset in range(0, len(ordered), per_sheet):
        batch = ordered[offset : offset + per_sheet]
        rows = (len(batch) + columns - 1) // columns
        canvas = Image.new(
            'RGB',
            (columns * card_width, rows * card_height),
            'white',
        )
        draw = ImageDraw.Draw(canvas)

        for index, page in enumerate(batch):
            image = _open_page_image(page)
            image.thumbnail((thumbnail_width, thumbnail_height), Image.Resampling.LANCZOS)
            column = index % columns
            row = index // columns
            card_x = column * card_width
            card_y = row * card_height
            label = f'PAGE {page.page_number}'
            draw.rectangle(
                (
                    card_x + 1,
                    card_y + 1,
                    card_x + card_width - 2,
                    card_y + card_height - 2,
                ),
                outline='#777777',
                width=1,
            )
            draw.text(
                (card_x + padding, card_y + padding),
                label,
                fill='black',
                font=font,
            )
            image_x = card_x + padding + (thumbnail_width - image.width) // 2
            image_y = card_y + padding + label_height + (
                thumbnail_height - image.height
            ) // 2
            canvas.paste(image, (image_x, image_y))

        output = io.BytesIO()
        canvas.save(output, format='JPEG', quality=72, optimize=True)
        data = output.getvalue()
        sheets.append(
            ContactSheet(
                page_numbers=tuple(page.page_number for page in batch),
                image=data,
                mime_type='image/jpeg',
                sha256=hashlib.sha256(data).hexdigest(),
            )
        )

    return tuple(sheets)


def _validate_sheet_coverage(
    *,
    contact_sheets: Iterable[ContactSheet],
    page_count: int,
) -> tuple[ContactSheet, ...]:
    sheets = tuple(contact_sheets)
    if not sheets:
        raise InvalidContactSheetInput('At least one contact sheet is required.')
    seen: set[int] = set()
    for sheet in sheets:
        if not sheet.image or not sheet.page_numbers:
            raise InvalidContactSheetInput('Every contact sheet must contain pages and image bytes.')
        for page_number in sheet.page_numbers:
            if page_number < 1 or page_number > page_count:
                raise InvalidContactSheetInput(
                    f'Contact-sheet page {page_number} is outside the PDF.'
                )
            if page_number in seen:
                raise InvalidContactSheetInput(
                    f'Page {page_number} appears in more than one contact sheet.'
                )
            seen.add(page_number)
    missing = sorted(set(range(1, page_count + 1)) - seen)
    if missing:
        raise InvalidContactSheetInput(
            f'Contact sheets do not cover source pages: {missing[:20]}'
        )
    return sheets


def _page_catalog(
    *,
    page_count: int,
    native_text_samples: dict[int, str] | None,
) -> list[dict[str, Any]]:
    sample_limit = _positive_int_env(
        'EXAM_PREP_V4_CLASSIFICATION_TEXT_SAMPLE_CHARS',
        600,
    )
    samples = native_text_samples or {}
    return [
        {
            'page_number': page_number,
            'native_text_sample': str(samples.get(page_number) or '')[:sample_limit],
        }
        for page_number in range(1, page_count + 1)
    ]


def _input_fingerprint(
    *,
    document: ExamSourceDocument,
    sheets: tuple[ContactSheet, ...],
    page_catalog: list[dict[str, Any]],
    model: str,
) -> str:
    payload = {
        'sourceSha256': document.source_sha256,
        'pageCount': document.page_count,
        'classificationRevision': document.classification_revision,
        'contactSheets': [
            {'pages': sheet.page_numbers, 'sha256': sheet.sha256}
            for sheet in sheets
        ],
        'pageCatalog': page_catalog,
        'model': model,
        'promptVersion': PROMPT_VERSION,
    }
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(',', ':'),
        ).encode('utf-8')
    ).hexdigest()


def _messages(
    *,
    page_catalog: list[dict[str, Any]],
    sheets: tuple[ContactSheet, ...],
) -> list[dict[str, Any]]:
    system_prompt = PROMPTS['exam_prep_v4_page_classification']['default']
    content: list[Any] = [
        {
            'type': 'text',
            'text': (
                'PAGE_CATALOG_JSON (source data):\n'
                + json.dumps(page_catalog, ensure_ascii=False, separators=(',', ':'))
            ),
        }
    ]
    for index, sheet in enumerate(sheets, start=1):
        content.append(
            {
                'type': 'text',
                'text': (
                    f'CONTACT_SHEET {index}; PDF pages: '
                    + ','.join(str(number) for number in sheet.page_numbers)
                ),
            }
        )
        content.append(part_from_bytes(data=sheet.image, mime_type=sheet.mime_type))
    return [
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': content},
    ]


def classify_document_pages_fast(
    *,
    document_id: int,
    expected_revision: int,
    contact_sheets: Iterable[ContactSheet],
    native_text_samples: dict[int, str] | None = None,
    model: str | None = None,
) -> FastClassifierResult:
    """Run one fast multimodal classification call and persist its page map."""

    document = ExamSourceDocument.objects.select_related('project').get(id=document_id)
    if document.classification_revision != expected_revision:
        from apps.classes.services.exam_prep_v4_classification import (
            StaleClassificationRevision,
        )

        raise StaleClassificationRevision(
            f'Expected revision {expected_revision}, current revision is '
            f'{document.classification_revision}.'
        )
    if document.page_count < 1:
        raise InvalidContactSheetInput('Source page count must be known first.')

    selected_model = _select_model(model)
    sheets = _validate_sheet_coverage(
        contact_sheets=contact_sheets,
        page_count=document.page_count,
    )
    catalog = _page_catalog(
        page_count=document.page_count,
        native_text_samples=native_text_samples,
    )
    fingerprint = _input_fingerprint(
        document=document,
        sheets=sheets,
        page_catalog=catalog,
        model=selected_model,
    )

    envelope = generate_structured(
        schema=FastClassificationEnvelope,
        messages=_messages(page_catalog=catalog, sheets=sheets),
        model=selected_model,
        feature=LLMUsageLog.Feature.PDF_EXTRACTION,
        timeout=_positive_float_env(
            'EXAM_PREP_V4_CLASSIFICATION_TIMEOUT_SECONDS',
            90.0,
        ),
        temperature=0,
        max_repair=1,
        sensitive=True,
        max_output_tokens=min(12_000, max(1_200, document.page_count * 90)),
        detail='exam_prep_v4_page_classification',
        tracking_context={
            'exam_project_id': document.project_id,
            'source_document_id': document.id,
            'revision': document.classification_revision,
            'page_count': document.page_count,
            'stage': 'page_classification',
            'prompt_version': PROMPT_VERSION,
        },
        provider_attempts=1,
    )
    persisted = persist_classification_result(
        document_id=document.id,
        expected_revision=expected_revision,
        fingerprint=fingerprint,
        raw_output={'pages': envelope.pages},
    )
    return FastClassifierResult(
        model=selected_model,
        prompt_version=PROMPT_VERSION,
        input_fingerprint=fingerprint,
        classification=persisted,
    )
