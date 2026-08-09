"""Private, on-demand source crops for the Exam Prep V4 projection.

The V4 database deliberately keeps the original rendered page as the
authority.  This module does not persist another image for every question;
it resolves the evidence fragments and stitches a bounded JPEG only when the
authenticated UI asks for it.  Consequently a crop can never become stale
when a teacher replaces a page render, and storage keys never enter the API
payload.
"""
from __future__ import annotations

from dataclasses import dataclass
import io
import os
from typing import Iterable, Sequence

from django.db.models import Prefetch
from PIL import Image

from apps.classes.models_v4 import ExamSourcePage
from apps.classes.models_v4_blocks import ExamSourceBlock, ExamSourceBlockFragment
from apps.classes.models_v4_records import (
    ExamAnswerSolutionRecord,
    ExamAnswerSolutionRecordEvidence,
    ExamExtractionLifecycle,
    ExamQuestionRecord,
    ExamQuestionRecordEvidence,
)


class SourceCropNotFound(LookupError):
    """The requested record or its private source render is unavailable."""


@dataclass(frozen=True, slots=True)
class _CropPart:
    image: Image.Image
    order: int


def source_crop_url(*, project_id: int, record_kind: str, record_id: int) -> str:
    """Return the stable relative URL used in the legacy projection JSON."""

    if record_kind not in {'question', 'solution'}:
        raise ValueError('record_kind must be question or solution')
    return (
        '/api/classes/exam-prep-source-crops/'
        f'{int(project_id)}/{record_kind}/{int(record_id)}/'
    )


def _positive_int_env(name: str, default: int, *, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def _record_and_evidence(
    *,
    project_id: int,
    record_kind: str,
    record_id: int,
) -> tuple[object, tuple[ExamSourceBlock, ...]]:
    """Resolve one accepted record and its ordered evidence blocks.

    We intentionally filter through both ``project_id`` and the record's
    document ancestry.  An integer record id alone must never be enough to
    read a private object from another project.
    """

    if record_kind == 'question':
        record_model = ExamQuestionRecord
        evidence_model = ExamQuestionRecordEvidence
    elif record_kind == 'solution':
        record_model = ExamAnswerSolutionRecord
        evidence_model = ExamAnswerSolutionRecordEvidence
    else:
        raise SourceCropNotFound('unsupported source crop kind')

    record = (
        record_model.objects.select_related('document', 'source_block')
        .filter(
            id=record_id,
            project_id=project_id,
            lifecycle_status=ExamExtractionLifecycle.ACCEPTED,
            document__project_id=project_id,
        )
        .first()
    )
    if record is None:
        raise SourceCropNotFound('record not found')
    if not record.source_block_id or not record.source_block:
        raise SourceCropNotFound('record has no source block')
    if record.source_block.document_id != record.document_id:
        raise SourceCropNotFound('record ancestry is inconsistent')

    evidence_ids = list(
        evidence_model.objects.filter(record_id=record.id)
        .order_by('order', 'id')
        .values_list('block_id', flat=True)
    )
    block_ids: list[int] = []
    for block_id in [record.source_block_id, *evidence_ids]:
        if block_id and block_id not in block_ids:
            block_ids.append(block_id)
    if not block_ids:
        raise SourceCropNotFound('record has no evidence blocks')

    fragment_queryset = ExamSourceBlockFragment.objects.select_related('page').order_by(
        'order', 'id'
    )
    blocks = tuple(
        ExamSourceBlock.objects.filter(
            id__in=block_ids,
            document_id=record.document_id,
            status=ExamSourceBlock.Status.ACCEPTED,
        ).prefetch_related(
            # ``to_attr`` avoids a second accidental query while rendering.
            # The normal related manager remains available to callers that do
            # not use this service.
            Prefetch(
                'fragments',
                queryset=fragment_queryset,
                to_attr='_crop_fragments',
            )
        )
    )
    by_id = {block.id: block for block in blocks}
    ordered_blocks = tuple(by_id[block_id] for block_id in block_ids if block_id in by_id)
    if not ordered_blocks or len(ordered_blocks) != len(block_ids):
        raise SourceCropNotFound('evidence blocks are unavailable')
    for block in ordered_blocks:
        fragments = getattr(block, '_crop_fragments', None)
        if not fragments:
            raise SourceCropNotFound('evidence block has no page fragments')
        if any(fragment.page.document_id != record.document_id for fragment in fragments):
            raise SourceCropNotFound('fragment page ancestry is inconsistent')
    return record, ordered_blocks


def _open_page(page: ExamSourcePage) -> Image.Image:
    if not page.rendered_file or not page.rendered_file.name:
        raise SourceCropNotFound('page render is unavailable')
    try:
        # Open through the FileField's private storage, never default media.
        with page.rendered_file.storage.open(page.rendered_file.name, 'rb') as handle:
            data = handle.read()
        image = Image.open(io.BytesIO(data))
        image.load()
        image = image.convert('RGB')
    except Exception as exc:
        # Storage backends may raise OSError, PIL errors, or provider-specific
        # exceptions (for example botocore ClientError).  They all represent
        # an unavailable private render at this boundary; never leak the
        # backend/storage error to an authenticated caller.
        raise SourceCropNotFound('page render is unreadable') from exc
    orientation = int(page.orientation or 0) % 360
    if orientation:
        image = image.rotate(-orientation, expand=True)
    return image


def _bounds(
    fragment: ExamSourceBlockFragment,
    width: int,
    height: int,
) -> tuple[int, int, int, int]:
    try:
        x0, y0, x1, y1 = (
            float(fragment.x0),
            float(fragment.y0),
            float(fragment.x1),
            float(fragment.y1),
        )
    except (TypeError, ValueError):
        raise SourceCropNotFound('fragment bbox is invalid')
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        raise SourceCropNotFound('fragment bbox is outside the page')
    try:
        requested_padding = float(
            os.getenv('EXAM_PREP_V4_SOURCE_CROP_PADDING', '0.008')
        )
    except (TypeError, ValueError):
        requested_padding = 0.008
    padding = min(0.03, max(0.0, requested_padding))
    pad_x = padding * width
    pad_y = padding * height
    left = max(0, min(width - 1, round(x0 * width - pad_x)))
    top = max(0, min(height - 1, round(y0 * height - pad_y)))
    right = max(left + 1, min(width, round(x1 * width + pad_x)))
    bottom = max(top + 1, min(height, round(y1 * height + pad_y)))
    return left, top, right, bottom


def _parts(blocks: Sequence[ExamSourceBlock]) -> list[_CropPart]:
    parts: list[_CropPart] = []
    page_cache: dict[int, Image.Image] = {}
    completed = False
    try:
        for block_order, block in enumerate(blocks):
            fragments: Iterable[ExamSourceBlockFragment] = getattr(
                block, '_crop_fragments', ()
            )
            for fragment in fragments:
                page = fragment.page
                page_image = page_cache.get(page.id)
                if page_image is None:
                    page_image = _open_page(page)
                    page_cache[page.id] = page_image
                left, top, right, bottom = _bounds(
                    fragment,
                    page_image.width,
                    page_image.height,
                )
                crop = page_image.crop((left, top, right, bottom))
                parts.append(_CropPart(crop, block_order * 1_000_000 + int(fragment.order)))
        if not parts:
            raise SourceCropNotFound('no source crop fragments')
        completed = True
        return parts
    finally:
        for image in page_cache.values():
            image.close()
        if not completed:
            for part in parts:
                part.image.close()


def _encode_stitched(parts: Sequence[_CropPart]) -> bytes:
    ordered = sorted(parts, key=lambda item: item.order)
    max_width = max(item.image.width for item in ordered)
    gap = min(256, _positive_int_env('EXAM_PREP_V4_SOURCE_CROP_GAP', 16))
    max_width_limit = _positive_int_env(
        'EXAM_PREP_V4_SOURCE_CROP_MAX_WIDTH',
        3200,
    )
    max_height_limit = _positive_int_env(
        'EXAM_PREP_V4_SOURCE_CROP_MAX_HEIGHT',
        24000,
    )
    max_width = min(max_width, max_width_limit)
    resized: list[Image.Image] = []
    temporary_images: list[Image.Image] = []
    try:
        total_height = 0
        for item in ordered:
            image = item.image
            if image.width > max_width:
                ratio = max_width / image.width
                image = image.resize(
                    (max_width, max(1, round(image.height * ratio))),
                    Image.Resampling.LANCZOS,
                )
                temporary_images.append(image)
            resized.append(image)
            total_height += image.height
        total_height += gap * max(0, len(resized) - 1)
        if total_height > max_height_limit:
            ratio = max_height_limit / total_height
            resized_height_limited: list[Image.Image] = []
            for image in resized:
                limited = image.resize(
                    (max(1, round(image.width * ratio)), max(1, round(image.height * ratio))),
                    Image.Resampling.LANCZOS,
                )
                temporary_images.append(limited)
                resized_height_limited.append(limited)
            resized = resized_height_limited
            image_height = sum(image.height for image in resized)
            available_gap = max_height_limit - image_height
            gap = min(
                gap,
                max(0, available_gap // max(1, len(resized) - 1)),
            )
            total_height = image_height + gap * max(0, len(resized) - 1)
        canvas = Image.new('RGB', (max_width, max(1, total_height)), 'white')
        try:
            y = 0
            for image in resized:
                x = max(0, (max_width - image.width) // 2)
                canvas.paste(image, (x, y))
                y += image.height + gap
            output = io.BytesIO()
            canvas.save(
                output,
                format='JPEG',
                quality=min(
                    100,
                    _positive_int_env(
                        'EXAM_PREP_V4_SOURCE_CROP_JPEG_QUALITY',
                        90,
                    ),
                ),
                optimize=True,
                progressive=True,
            )
            data = output.getvalue()
        finally:
            canvas.close()
    finally:
        # ``parts`` own the original crop images.  Resized images are also
        # closed here, including width-limited images that were replaced by a
        # second height-limited copy.
        originals = {id(item.image): item.image for item in ordered}
        closed: set[int] = set()
        for image in temporary_images:
            if id(image) not in originals and id(image) not in closed:
                image.close()
                closed.add(id(image))
        for image in originals.values():
            if id(image) not in closed:
                image.close()
                closed.add(id(image))
    max_bytes = _positive_int_env(
        'EXAM_PREP_V4_SOURCE_CROP_MAX_BYTES',
        8 * 1024 * 1024,
    )
    if len(data) > max_bytes:
        raise SourceCropNotFound('source crop exceeds the bounded byte limit')
    return data


def render_source_crop(
    *,
    project_id: int,
    record_kind: str,
    record_id: int,
) -> bytes:
    """Render one accepted question/solution evidence crop as a JPEG."""

    _record, blocks = _record_and_evidence(
        project_id=project_id,
        record_kind=record_kind,
        record_id=record_id,
    )
    return _encode_stitched(_parts(blocks))


__all__ = [
    'SourceCropNotFound',
    'render_source_crop',
    'source_crop_url',
]
