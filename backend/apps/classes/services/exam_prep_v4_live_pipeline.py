"""Provider-neutral full semantic extraction runner for Exam Prep V4.

Fake and live providers share the same authoritative persistence path. Provider
output may propose structure and source transcription only; confirmed source
scope, block identity, revisions, fingerprints, and automatic matching remain
server-owned.
"""
from __future__ import annotations

from dataclasses import dataclass
import io
import json
import os
from typing import Any, Iterable, Protocol, Sequence

from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field

from apps.chatbot.services.llm_client import part_from_bytes
from apps.classes.models_v4 import (
    ExamProject,
    ExamSourceDocument,
    ExamSourcePage,
    ExamSourceRole,
    ExamSourceSegment,
)
from apps.classes.models_v4_blocks import ExamSourceBlock, ExamSourceBlockKind
from apps.classes.models_v4_records import (
    ExamAnswerSolutionRecord,
    ExamExtractionLifecycle,
    ExamQuestionRecord,
)
from apps.classes.services.exam_prep_v4_blocks import (
    PersistedBlockSet,
    SourceBlockProposal,
    parse_block_detector_output,
    persist_source_blocks,
)
from apps.classes.services.exam_prep_v4_records import (
    AnswerSolutionRecordProposal,
    PersistedMatchSet,
    PersistedRecordSet,
    QuestionOptionProposal,
    QuestionRecordProposal,
    build_deterministic_matches,
    parse_answer_solution_extraction_output,
    parse_question_extraction_output,
    persist_answer_solution_records,
    persist_question_records,
)
from apps.commons.llm_prompts import PROMPTS
from apps.commons.models import LLMUsageLog
from apps.commons.structured_llm import generate_structured


BLOCK_PROMPT_VERSION = 'exam-prep-v4-block-detection-v1'
QUESTION_PROMPT_VERSION = 'exam-prep-v4-question-extraction-v2-batched'
ANSWER_PROMPT_VERSION = 'exam-prep-v4-answer-solution-extraction-v2-batched'


class ExtractionPipelineConfigurationError(RuntimeError):
    pass


class ExtractionImageError(RuntimeError):
    pass


class BlockDetectionEnvelope(BaseModel):
    model_config = ConfigDict(extra='ignore')
    blocks: list[Any] = Field(default_factory=list)


class QuestionExtractionEnvelope(BaseModel):
    model_config = ConfigDict(extra='ignore')
    questions: list[Any] = Field(default_factory=list)


class AnswerExtractionEnvelope(BaseModel):
    model_config = ConfigDict(extra='ignore')
    answers: list[Any] = Field(default_factory=list)


@dataclass(frozen=True, slots=True)
class PreparedVisionImage:
    image: bytes
    mime_type: str
    page_number: int
    label: str


@dataclass(frozen=True, slots=True)
class PreparedBlockExtraction:
    """One authoritative block and its bounded, ordered private crop payload."""

    block: ExamSourceBlock
    images: tuple[PreparedVisionImage, ...]
    evidence_blocks: tuple[ExamSourceBlock, ...] = ()

    @property
    def byte_size(self) -> int:
        return sum(len(image.image) for image in self.images)


@dataclass(frozen=True, slots=True)
class StageIssue:
    stage: str
    code: str
    block_id: int | None = None
    segment_order: int | None = None
    batch_index: int | None = None
    retryable: bool = False


@dataclass(frozen=True, slots=True)
class FullExtractionResult:
    document_id: int
    project_id: int
    block_set: PersistedBlockSet
    question_set: PersistedRecordSet
    answer_set: PersistedRecordSet
    matches: PersistedMatchSet
    issues: tuple[StageIssue, ...]
    provider_calls: int


class ExamPrepV4ExtractionProvider(Protocol):
    provider_calls: int

    def detect_segment_blocks(
        self,
        *,
        document: ExamSourceDocument,
        segment: ExamSourceSegment,
        pages: Sequence[ExamSourcePage],
        images: Sequence[PreparedVisionImage],
    ) -> Any: ...

    def extract_question(
        self,
        *,
        document: ExamSourceDocument,
        block: ExamSourceBlock,
        images: Sequence[PreparedVisionImage],
    ) -> Any: ...

    def extract_answer_solution(
        self,
        *,
        document: ExamSourceDocument,
        block: ExamSourceBlock,
        evidence_blocks: Sequence[ExamSourceBlock],
        images: Sequence[PreparedVisionImage],
    ) -> Any: ...


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


def _select_model(explicit: str | None, env_name: str) -> str:
    model = (
        (explicit or '').strip()
        or (os.getenv(env_name) or '').strip()
        or (os.getenv('PDF_VISION_MODEL') or '').strip()
        or (os.getenv('MODEL_NAME') or '').strip()
    )
    if not model:
        raise ExtractionPipelineConfigurationError(
            f'Set {env_name}, PDF_VISION_MODEL, or MODEL_NAME.'
        )
    return model.removeprefix('models/')


def _open_oriented_page(page: ExamSourcePage) -> Image.Image:
    if not page.rendered_file:
        raise ExtractionImageError(
            f'Source page {page.page_number} has no private rendered image.'
        )
    try:
        with page.rendered_file.open('rb') as handle:
            data = handle.read()
        image = Image.open(io.BytesIO(data))
        image.load()
        image = image.convert('RGB')
    except (OSError, UnidentifiedImageError) as exc:
        raise ExtractionImageError(
            f'Source page {page.page_number} render is unreadable.'
        ) from exc
    if page.orientation:
        image = image.rotate(-int(page.orientation), expand=True)
    return image


def _encode_bounded_jpeg(image: Image.Image, *, max_dimension: int) -> bytes:
    bounded = image.copy()
    bounded.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
    output = io.BytesIO()
    bounded.save(
        output,
        format='JPEG',
        quality=_positive_int_env('EXAM_PREP_V4_VISION_JPEG_QUALITY', 84),
        optimize=True,
    )
    data = output.getvalue()
    max_bytes = _positive_int_env(
        'EXAM_PREP_V4_VISION_IMAGE_MAX_BYTES',
        4 * 1024 * 1024,
    )
    if len(data) > max_bytes:
        raise ExtractionImageError(
            'Prepared vision image exceeds the bounded byte limit.'
        )
    return data


def prepare_full_page_image(page: ExamSourcePage) -> PreparedVisionImage:
    image = _open_oriented_page(page)
    data = _encode_bounded_jpeg(
        image,
        max_dimension=_positive_int_env(
            'EXAM_PREP_V4_BLOCK_PAGE_MAX_DIMENSION',
            1600,
        ),
    )
    return PreparedVisionImage(
        image=data,
        mime_type='image/jpeg',
        page_number=page.page_number,
        label=f'PAGE {page.page_number}',
    )


def prepare_block_crop_images(
    block: ExamSourceBlock,
    *,
    evidence_blocks: Sequence[ExamSourceBlock] | None = None,
) -> tuple[PreparedVisionImage, ...]:
    blocks = tuple(evidence_blocks or (block,))
    prepared: list[PreparedVisionImage] = []
    crop_index = 0
    for evidence_block in blocks:
        fragments = evidence_block.fragments.select_related('page').order_by('order')
        for fragment in fragments:
            page_image = _open_oriented_page(fragment.page)
            width, height = page_image.size
            left = max(0, min(width - 1, round(float(fragment.x0) * width)))
            top = max(0, min(height - 1, round(float(fragment.y0) * height)))
            right = max(left + 1, min(width, round(float(fragment.x1) * width)))
            bottom = max(top + 1, min(height, round(float(fragment.y1) * height)))
            crop = page_image.crop((left, top, right, bottom))
            data = _encode_bounded_jpeg(
                crop,
                max_dimension=_positive_int_env(
                    'EXAM_PREP_V4_BLOCK_CROP_MAX_DIMENSION',
                    2200,
                ),
            )
            prepared.append(
                PreparedVisionImage(
                    image=data,
                    mime_type='image/jpeg',
                    page_number=fragment.page.page_number,
                    label=(
                        f'CROP {crop_index}; PAGE {fragment.page.page_number}; '
                        f'BLOCK_ORDER {evidence_block.order}; '
                        f'FRAGMENT_ORDER {fragment.order}'
                    ),
                )
            )
            crop_index += 1
    if not prepared:
        raise ExtractionImageError(f'Block {block.id} has no evidence crop.')
    return tuple(prepared)


def _vision_content(
    prefix: str,
    images: Sequence[PreparedVisionImage],
) -> list[Any]:
    content: list[Any] = [{'type': 'text', 'text': prefix}]
    for image in images:
        content.append({'type': 'text', 'text': image.label})
        content.append(part_from_bytes(data=image.image, mime_type=image.mime_type))
    return content


def _batch_vision_content(
    prefix: str,
    items: Sequence[PreparedBlockExtraction],
) -> list[Any]:
    content: list[Any] = [{'type': 'text', 'text': prefix}]
    for item in items:
        content.append(
            {
                'type': 'text',
                'text': (
                    f'AUTHORITATIVE_BLOCK_START {item.block.id}; '
                    f'IMAGE_COUNT {len(item.images)}'
                ),
            }
        )
        for image in item.images:
            content.append(
                {
                    'type': 'text',
                    'text': f'BLOCK {item.block.id}; {image.label}',
                }
            )
            content.append(
                part_from_bytes(data=image.image, mime_type=image.mime_type)
            )
        content.append(
            {
                'type': 'text',
                'text': f'AUTHORITATIVE_BLOCK_END {item.block.id}',
            }
        )
    return content


def bounded_extraction_batches(
    items: Iterable[PreparedBlockExtraction],
) -> tuple[tuple[PreparedBlockExtraction, ...], ...]:
    """Bound provider payloads by block count, image count, and total bytes."""

    max_blocks = _positive_int_env(
        'EXAM_PREP_V4_EXTRACTION_BATCH_MAX_BLOCKS',
        4,
    )
    max_images = _positive_int_env(
        'EXAM_PREP_V4_EXTRACTION_BATCH_MAX_IMAGES',
        12,
    )
    max_bytes = _positive_int_env(
        'EXAM_PREP_V4_EXTRACTION_BATCH_MAX_BYTES',
        12 * 1024 * 1024,
    )
    batches: list[tuple[PreparedBlockExtraction, ...]] = []
    current: list[PreparedBlockExtraction] = []
    current_images = 0
    current_bytes = 0

    for item in items:
        image_count = len(item.images)
        byte_size = item.byte_size
        if image_count > max_images or byte_size > max_bytes:
            raise ExtractionImageError(
                f'Block {item.block.id} exceeds the bounded batch payload.'
            )
        exceeds = current and (
            len(current) + 1 > max_blocks
            or current_images + image_count > max_images
            or current_bytes + byte_size > max_bytes
        )
        if exceeds:
            batches.append(tuple(current))
            current = []
            current_images = 0
            current_bytes = 0
        current.append(item)
        current_images += image_count
        current_bytes += byte_size

    if current:
        batches.append(tuple(current))
    return tuple(batches)


class StructuredLLMExamPrepV4Provider:
    """Live structured provider using the repository's existing AvalAI gateway."""

    def __init__(
        self,
        *,
        block_model: str | None = None,
        question_model: str | None = None,
        answer_model: str | None = None,
    ) -> None:
        self.block_model = _select_model(block_model, 'EXAM_PREP_V4_BLOCK_MODEL')
        self.question_model = _select_model(
            question_model,
            'EXAM_PREP_V4_QUESTION_MODEL',
        )
        self.answer_model = _select_model(
            answer_model,
            'EXAM_PREP_V4_ANSWER_MODEL',
        )
        self.provider_calls = 0

    def _generate(
        self,
        *,
        schema,
        prompt_key: str,
        content: list[Any],
        model: str,
        detail: str,
        document: ExamSourceDocument,
        tracking: dict[str, Any],
        max_output_tokens: int,
    ):
        self.provider_calls += 1
        return generate_structured(
            schema=schema,
            messages=[
                {'role': 'system', 'content': PROMPTS[prompt_key]['default']},
                {'role': 'user', 'content': content},
            ],
            model=model,
            feature=LLMUsageLog.Feature.PDF_EXTRACTION,
            timeout=_positive_float_env(
                'EXAM_PREP_V4_EXTRACTION_TIMEOUT_SECONDS',
                180.0,
            ),
            temperature=0,
            max_repair=1,
            sensitive=True,
            max_output_tokens=max_output_tokens,
            detail=detail,
            tracking_context={
                'exam_project_id': document.project_id,
                'source_document_id': document.id,
                **tracking,
            },
            provider_attempts=1,
        )

    def detect_segment_blocks(
        self,
        *,
        document: ExamSourceDocument,
        segment: ExamSourceSegment,
        pages: Sequence[ExamSourcePage],
        images: Sequence[PreparedVisionImage],
    ) -> Any:
        prefix = (
            'AUTHORITATIVE_SEGMENT_JSON:\n'
            + json.dumps(
                {
                    'segmentOrder': segment.order,
                    'role': segment.role,
                    'pageNumbers': [page.page_number for page in pages],
                },
                ensure_ascii=False,
                separators=(',', ':'),
            )
        )
        envelope = self._generate(
            schema=BlockDetectionEnvelope,
            prompt_key='exam_prep_v4_block_detection',
            content=_vision_content(prefix, images),
            model=self.block_model,
            detail='exam_prep_v4_block_detection',
            document=document,
            tracking={
                'stage': 'block_detection',
                'segment_order': segment.order,
                'segment_role': segment.role,
                'prompt_version': BLOCK_PROMPT_VERSION,
            },
            max_output_tokens=min(20_000, max(2_000, len(pages) * 1_800)),
        )
        return {'blocks': envelope.blocks}

    def extract_questions_batch(
        self,
        *,
        document: ExamSourceDocument,
        items: Sequence[PreparedBlockExtraction],
        batch_index: int,
    ) -> Any:
        authoritative = {
            'batchIndex': batch_index,
            'blocks': [
                {
                    'blockId': item.block.id,
                    'kind': item.block.kind,
                    'printedNumber': item.block.printed_number,
                    'sectionKey': item.block.segment.section_key,
                    'imageCount': len(item.images),
                }
                for item in items
            ],
        }
        prefix = (
            'AUTHORITATIVE_BLOCK_BATCH_JSON:\n'
            + json.dumps(
                authoritative,
                ensure_ascii=False,
                separators=(',', ':'),
            )
        )
        envelope = self._generate(
            schema=QuestionExtractionEnvelope,
            prompt_key='exam_prep_v4_question_extraction',
            content=_batch_vision_content(prefix, items),
            model=self.question_model,
            detail='exam_prep_v4_question_extraction_batch',
            document=document,
            tracking={
                'stage': 'question_extraction',
                'batch_index': batch_index,
                'batch_size': len(items),
                'source_block_ids': [item.block.id for item in items],
                'block_fingerprints': [
                    item.block.fingerprint for item in items
                ],
                'prompt_version': QUESTION_PROMPT_VERSION,
            },
            max_output_tokens=min(
                _positive_int_env(
                    'EXAM_PREP_V4_QUESTION_BATCH_MAX_OUTPUT_TOKENS',
                    24_000,
                ),
                max(8_000, len(items) * 6_000),
            ),
        )
        return {'questions': envelope.questions}

    def extract_answer_solutions_batch(
        self,
        *,
        document: ExamSourceDocument,
        items: Sequence[PreparedBlockExtraction],
        batch_index: int,
    ) -> Any:
        authoritative = {
            'batchIndex': batch_index,
            'blocks': [
                {
                    'blockId': item.block.id,
                    'kind': item.block.kind,
                    'printedNumber': item.block.printed_number,
                    'sectionKey': item.block.segment.section_key,
                    'evidenceBlockOrders': [
                        block.order for block in item.evidence_blocks
                    ],
                    'imageCount': len(item.images),
                }
                for item in items
            ],
        }
        prefix = (
            'AUTHORITATIVE_BLOCK_BATCH_JSON:\n'
            + json.dumps(
                authoritative,
                ensure_ascii=False,
                separators=(',', ':'),
            )
        )
        envelope = self._generate(
            schema=AnswerExtractionEnvelope,
            prompt_key='exam_prep_v4_answer_solution_extraction',
            content=_batch_vision_content(prefix, items),
            model=self.answer_model,
            detail='exam_prep_v4_answer_solution_extraction_batch',
            document=document,
            tracking={
                'stage': 'answer_solution_extraction',
                'batch_index': batch_index,
                'batch_size': len(items),
                'source_block_ids': [item.block.id for item in items],
                'block_fingerprints': [
                    item.block.fingerprint for item in items
                ],
                'prompt_version': ANSWER_PROMPT_VERSION,
            },
            max_output_tokens=min(
                _positive_int_env(
                    'EXAM_PREP_V4_ANSWER_BATCH_MAX_OUTPUT_TOKENS',
                    32_000,
                ),
                max(12_000, len(items) * 10_000),
            ),
        )
        return {'answers': envelope.answers}

    def extract_question(
        self,
        *,
        document: ExamSourceDocument,
        block: ExamSourceBlock,
        images: Sequence[PreparedVisionImage],
    ) -> Any:
        """Single-block compatibility path used by block-specific escalation."""

        return self.extract_questions_batch(
            document=document,
            items=(
                PreparedBlockExtraction(
                    block=block,
                    images=tuple(images),
                ),
            ),
            batch_index=0,
        )

    def extract_answer_solution(
        self,
        *,
        document: ExamSourceDocument,
        block: ExamSourceBlock,
        evidence_blocks: Sequence[ExamSourceBlock],
        images: Sequence[PreparedVisionImage],
    ) -> Any:
        """Single-block compatibility path used by block-specific escalation."""

        return self.extract_answer_solutions_batch(
            document=document,
            items=(
                PreparedBlockExtraction(
                    block=block,
                    evidence_blocks=tuple(evidence_blocks),
                    images=tuple(images),
                ),
            ),
            batch_index=0,
        )


def _segment_page_numbers(
    segment: ExamSourceSegment,
    ordered_pages: Sequence[ExamSourcePage],
) -> tuple[int, ...]:
    raw = (segment.metadata or {}).get('pageNumbers')
    if isinstance(raw, list) and raw:
        try:
            return tuple(int(value) for value in raw)
        except (TypeError, ValueError):
            pass
    by_number = {
        page.page_number: index for index, page in enumerate(ordered_pages)
    }
    start = by_number[segment.start_page]
    end = by_number[segment.end_page]
    low, high = sorted((start, end))
    sequence = tuple(
        page.page_number for page in ordered_pages[low : high + 1]
    )
    return sequence if start <= end else tuple(reversed(sequence))


def _current_confirmed_scope(
    document: ExamSourceDocument,
) -> tuple[tuple[ExamSourcePage, ...], tuple[ExamSourceSegment, ...]]:
    if not (
        document.status == ExamSourceDocument.Status.CONFIRMED
        and document.teacher_confirmed_revision == document.classification_revision
        and document.teacher_confirmed_fingerprint
        == document.source_map_fingerprint
        and document.teacher_confirmed_at is not None
    ):
        raise ExtractionPipelineConfigurationError(
            'The exact current Source Map must be teacher-confirmed first.'
        )
    pages = tuple(
        ExamSourcePage.objects.filter(document=document).order_by(
            'display_order',
            'page_number',
        )
    )
    segments = tuple(
        ExamSourceSegment.objects.filter(
            document=document,
            revision=document.classification_revision,
            teacher_confirmed=True,
            status=ExamSourceSegment.Status.CONFIRMED,
        ).order_by('order')
    )
    if len(pages) != document.page_count or not segments:
        raise ExtractionPipelineConfigurationError(
            'Confirmed Source Map is incomplete.'
        )
    return pages, segments


def _existing_current_blocks(
    document: ExamSourceDocument,
) -> tuple[ExamSourceBlock, ...]:
    candidates = tuple(
        ExamSourceBlock.objects.filter(
            document=document,
            source_map_fingerprint=document.source_map_fingerprint,
            status=ExamSourceBlock.Status.ACCEPTED,
        ).order_by('-revision', 'order')
    )
    if not candidates:
        return ()
    revision = max(block.revision for block in candidates)
    return tuple(block for block in candidates if block.revision == revision)


def _block_set_result(
    blocks: Sequence[ExamSourceBlock],
) -> PersistedBlockSet:
    return PersistedBlockSet(
        document_id=blocks[0].document_id,
        revision=blocks[0].revision,
        source_map_fingerprint=blocks[0].source_map_fingerprint,
        set_fingerprint=blocks[0].set_fingerprint,
        block_count=len(blocks),
        fragment_count=sum(block.fragments.count() for block in blocks),
        reused=True,
    )


def _detect_blocks(
    *,
    document: ExamSourceDocument,
    provider: ExamPrepV4ExtractionProvider,
) -> tuple[PersistedBlockSet, tuple[StageIssue, ...]]:
    current = _existing_current_blocks(document)
    if current:
        return _block_set_result(current), ()

    pages, segments = _current_confirmed_scope(document)
    pages_by_number = {page.page_number: page for page in pages}
    global_proposals: list[SourceBlockProposal] = []
    issues: list[StageIssue] = []

    for segment in segments:
        if segment.role in {ExamSourceRole.COVER, ExamSourceRole.IGNORED}:
            continue
        numbers = _segment_page_numbers(segment, pages)
        segment_pages = tuple(pages_by_number[number] for number in numbers)
        images = tuple(
            prepare_full_page_image(page) for page in segment_pages
        )
        raw = provider.detect_segment_blocks(
            document=document,
            segment=segment,
            pages=segment_pages,
            images=images,
        )
        records = raw.get('blocks', []) if isinstance(raw, dict) else []
        enriched: list[Any] = []
        for record in records:
            if not isinstance(record, dict):
                enriched.append(record)
                continue
            item = dict(record)
            item['segmentOrder'] = segment.order
            enriched.append(item)

        parsed = parse_block_detector_output({'blocks': enriched})
        for issue in parsed.issues:
            issues.append(
                StageIssue(
                    stage='block_detection',
                    code=issue.code,
                    segment_order=segment.order,
                )
            )

        local_to_global: dict[int, int] = {}
        for local in parsed.blocks:
            local_to_global[local.order] = len(global_proposals)
            global_proposals.append(
                SourceBlockProposal(
                    order=len(global_proposals),
                    segment_order=segment.order,
                    kind=local.kind,
                    fragments=local.fragments,
                    printed_number=local.printed_number,
                    confidence=local.confidence,
                    continuation_of_order=None,
                    metadata=dict(local.metadata),
                )
            )

        start_index = len(global_proposals) - len(parsed.blocks)
        for index, local in enumerate(parsed.blocks):
            if local.continuation_of_order is None:
                continue
            parent = local_to_global.get(local.continuation_of_order)
            if parent is None:
                issues.append(
                    StageIssue(
                        stage='block_detection',
                        code='missing_continuation_parent',
                        segment_order=segment.order,
                    )
                )
                continue
            current = global_proposals[start_index + index]
            global_proposals[start_index + index] = SourceBlockProposal(
                order=current.order,
                segment_order=current.segment_order,
                kind=current.kind,
                fragments=current.fragments,
                printed_number=current.printed_number,
                confidence=current.confidence,
                continuation_of_order=parent,
                metadata=current.metadata,
            )

    if not global_proposals:
        raise ExtractionPipelineConfigurationError(
            'Block detector produced no valid blocks for the confirmed source map.'
        )
    result = persist_source_blocks(
        document_id=document.id,
        expected_source_map_revision=document.classification_revision,
        expected_source_map_fingerprint=document.source_map_fingerprint,
        proposals=tuple(global_proposals),
    )
    return result, tuple(issues)


def _question_blocks_for_set(
    document: ExamSourceDocument,
    block_set: PersistedBlockSet,
) -> tuple[ExamSourceBlock, ...]:
    return tuple(
        ExamSourceBlock.objects.filter(
            document=document,
            revision=block_set.revision,
            set_fingerprint=block_set.set_fingerprint,
            status=ExamSourceBlock.Status.ACCEPTED,
            kind__in=[
                ExamSourceBlockKind.QUESTION,
                ExamSourceBlockKind.INLINE_QUESTION_ANSWER,
            ],
        )
        .select_related('segment')
        .order_by('order')
    )


def _answer_blocks_for_set(
    document: ExamSourceDocument,
    block_set: PersistedBlockSet,
) -> tuple[ExamSourceBlock, ...]:
    return tuple(
        ExamSourceBlock.objects.filter(
            document=document,
            revision=block_set.revision,
            set_fingerprint=block_set.set_fingerprint,
            status=ExamSourceBlock.Status.ACCEPTED,
        )
        .select_related('segment', 'continuation_of')
        .order_by('order')
    )


def _accepted_question_records(
    document: ExamSourceDocument,
    block_fingerprint: str,
) -> tuple[ExamQuestionRecord, ...]:
    return tuple(
        ExamQuestionRecord.objects.filter(
            document=document,
            block_set_fingerprint=block_fingerprint,
            lifecycle_status=ExamExtractionLifecycle.ACCEPTED,
            source_block__status=ExamSourceBlock.Status.ACCEPTED,
        )
        .select_related('source_block')
        .order_by('order')
    )


def _accepted_answer_records(
    document: ExamSourceDocument,
    block_fingerprint: str,
) -> tuple[ExamAnswerSolutionRecord, ...]:
    return tuple(
        ExamAnswerSolutionRecord.objects.filter(
            document=document,
            block_set_fingerprint=block_fingerprint,
            lifecycle_status=ExamExtractionLifecycle.ACCEPTED,
            source_block__status=ExamSourceBlock.Status.ACCEPTED,
        )
        .select_related('source_block')
        .order_by('order')
    )


def _record_set_result(
    *,
    document_id: int,
    block_fingerprint: str,
    records: Sequence[Any],
) -> PersistedRecordSet:
    return PersistedRecordSet(
        document_id=document_id,
        revision=records[0].revision,
        block_set_fingerprint=block_fingerprint,
        set_fingerprint=records[0].set_fingerprint,
        record_count=len(records),
        evidence_link_count=sum(
            record.evidence_links.count() for record in records
        ),
        reused=True,
    )


def _question_proposal_from_record(
    record: ExamQuestionRecord,
) -> QuestionRecordProposal:
    options: list[QuestionOptionProposal] = []
    if isinstance(record.options, list):
        for option in record.options:
            if not isinstance(option, dict):
                continue
            label = str(option.get('label') or '').strip()
            if not label:
                continue
            options.append(
                QuestionOptionProposal(
                    label=label,
                    text=str(option.get('text') or ''),
                )
            )
    return QuestionRecordProposal(
        block_id=record.source_block_id,
        question_text=record.question_text,
        printed_number=record.printed_number,
        section_key=record.section_key,
        options=tuple(options),
        confidence=float(record.confidence),
        warnings=tuple(record.warnings or ()),
        raw_payload=dict(record.raw_payload or {}),
    )


def _answer_proposal_from_record(
    record: ExamAnswerSolutionRecord,
) -> AnswerSolutionRecordProposal:
    return AnswerSolutionRecordProposal(
        block_id=record.source_block_id,
        printed_number=record.printed_number,
        section_key=record.section_key,
        correct_option=record.correct_option,
        final_answer=record.final_answer,
        solution_text=record.solution_text,
        confidence=float(record.confidence),
        warnings=tuple(record.warnings or ()),
        raw_payload=dict(record.raw_payload or {}),
    )


def _legacy_question_batch(
    *,
    provider: ExamPrepV4ExtractionProvider,
    document: ExamSourceDocument,
    items: Sequence[PreparedBlockExtraction],
) -> Any:
    records: list[Any] = []
    for item in items:
        raw = provider.extract_question(
            document=document,
            block=item.block,
            images=item.images,
        )
        if isinstance(raw, dict) and isinstance(raw.get('questions'), list):
            records.extend(raw['questions'])
    return {'questions': records}


def _legacy_answer_batch(
    *,
    provider: ExamPrepV4ExtractionProvider,
    document: ExamSourceDocument,
    items: Sequence[PreparedBlockExtraction],
) -> Any:
    records: list[Any] = []
    for item in items:
        raw = provider.extract_answer_solution(
            document=document,
            block=item.block,
            evidence_blocks=item.evidence_blocks,
            images=item.images,
        )
        if isinstance(raw, dict) and isinstance(raw.get('answers'), list):
            records.extend(raw['answers'])
    return {'answers': records}


def _question_batch_output(
    *,
    provider: ExamPrepV4ExtractionProvider,
    document: ExamSourceDocument,
    items: Sequence[PreparedBlockExtraction],
    batch_index: int,
) -> Any:
    method = getattr(provider, 'extract_questions_batch', None)
    if callable(method):
        return method(
            document=document,
            items=items,
            batch_index=batch_index,
        )
    return _legacy_question_batch(
        provider=provider,
        document=document,
        items=items,
    )


def _answer_batch_output(
    *,
    provider: ExamPrepV4ExtractionProvider,
    document: ExamSourceDocument,
    items: Sequence[PreparedBlockExtraction],
    batch_index: int,
) -> Any:
    method = getattr(provider, 'extract_answer_solutions_batch', None)
    if callable(method):
        return method(
            document=document,
            items=items,
            batch_index=batch_index,
        )
    return _legacy_answer_batch(
        provider=provider,
        document=document,
        items=items,
    )


def _parse_issue_block_id(issue, expected_ids: set[int]) -> int | None:
    return issue.block_id if issue.block_id in expected_ids else None


def _extract_questions(
    *,
    document: ExamSourceDocument,
    block_set: PersistedBlockSet,
    provider: ExamPrepV4ExtractionProvider,
) -> tuple[PersistedRecordSet, tuple[StageIssue, ...]]:
    blocks = _question_blocks_for_set(document, block_set)
    expected_ids = {block.id for block in blocks}
    accepted = _accepted_question_records(
        document,
        block_set.set_fingerprint,
    )
    accepted_by_block = {
        record.source_block_id: record
        for record in accepted
        if record.source_block_id in expected_ids
    }
    if expected_ids and set(accepted_by_block) == expected_ids:
        return _record_set_result(
            document_id=document.id,
            block_fingerprint=block_set.set_fingerprint,
            records=tuple(accepted_by_block[block.id] for block in blocks),
        ), ()

    missing_blocks = tuple(
        block for block in blocks if block.id not in accepted_by_block
    )
    items = (
        PreparedBlockExtraction(
            block=block,
            images=prepare_block_crop_images(block),
        )
        for block in missing_blocks
    )

    proposals: list[QuestionRecordProposal] = [
        _question_proposal_from_record(accepted_by_block[block.id])
        for block in blocks
        if block.id in accepted_by_block
    ]
    issues: list[StageIssue] = []
    for batch_index, batch in enumerate(bounded_extraction_batches(items)):
        batch_expected_ids = {item.block.id for item in batch}
        raw = _question_batch_output(
            provider=provider,
            document=document,
            items=batch,
            batch_index=batch_index,
        )
        parsed = parse_question_extraction_output(raw)
        for issue in parsed.issues:
            issues.append(
                StageIssue(
                    stage='question_extraction',
                    code=issue.code,
                    block_id=_parse_issue_block_id(
                        issue,
                        batch_expected_ids,
                    ),
                    batch_index=batch_index,
                    retryable=True,
                )
            )

        returned_ids: set[int] = set()
        for record in parsed.records:
            if record.block_id not in batch_expected_ids:
                issues.append(
                    StageIssue(
                        stage='question_extraction',
                        code='unexpected_question_block_id',
                        block_id=record.block_id,
                        batch_index=batch_index,
                    )
                )
                continue
            returned_ids.add(record.block_id)
            proposals.append(record)

        for missing_id in sorted(batch_expected_ids - returned_ids):
            issues.append(
                StageIssue(
                    stage='question_extraction',
                    code='missing_question_block_id',
                    block_id=missing_id,
                    batch_index=batch_index,
                    retryable=True,
                )
            )

    if not proposals:
        raise ExtractionPipelineConfigurationError(
            'No valid question records were extracted.'
        )
    result = persist_question_records(
        document_id=document.id,
        expected_block_set_fingerprint=block_set.set_fingerprint,
        proposals=tuple(proposals),
    )
    return result, tuple(issues)


def _continuation_chain(
    primary: ExamSourceBlock,
    blocks: Sequence[ExamSourceBlock],
) -> tuple[ExamSourceBlock, ...]:
    by_parent: dict[int, list[ExamSourceBlock]] = {}
    for block in blocks:
        if block.continuation_of_id:
            by_parent.setdefault(block.continuation_of_id, []).append(block)
    for values in by_parent.values():
        values.sort(key=lambda item: item.order)

    result: list[ExamSourceBlock] = []
    seen: set[int] = set()

    def add(block: ExamSourceBlock) -> None:
        if block.id in seen:
            raise ExtractionPipelineConfigurationError(
                'Continuation evidence contains a cycle.'
            )
        seen.add(block.id)
        result.append(block)
        for child in by_parent.get(block.id, []):
            add(child)

    add(primary)
    return tuple(result)


def _extract_answers(
    *,
    document: ExamSourceDocument,
    block_set: PersistedBlockSet,
    provider: ExamPrepV4ExtractionProvider,
) -> tuple[PersistedRecordSet, tuple[StageIssue, ...]]:
    all_blocks = _answer_blocks_for_set(document, block_set)
    primaries = tuple(
        block
        for block in all_blocks
        if block.kind
        in {
            ExamSourceBlockKind.ANSWER_SOLUTION,
            ExamSourceBlockKind.ANSWER_KEY,
            ExamSourceBlockKind.INLINE_QUESTION_ANSWER,
        }
    )
    expected_ids = {block.id for block in primaries}
    accepted = _accepted_answer_records(
        document,
        block_set.set_fingerprint,
    )
    accepted_by_block = {
        record.source_block_id: record
        for record in accepted
        if record.source_block_id in expected_ids
    }
    if expected_ids and set(accepted_by_block) == expected_ids:
        return _record_set_result(
            document_id=document.id,
            block_fingerprint=block_set.set_fingerprint,
            records=tuple(accepted_by_block[block.id] for block in primaries),
        ), ()

    missing_blocks = tuple(
        block for block in primaries if block.id not in accepted_by_block
    )

    def prepared_items():
        for block in missing_blocks:
            chain = _continuation_chain(block, all_blocks)
            yield PreparedBlockExtraction(
                block=block,
                evidence_blocks=chain,
                images=prepare_block_crop_images(
                    block,
                    evidence_blocks=chain,
                ),
            )

    proposals: list[AnswerSolutionRecordProposal] = [
        _answer_proposal_from_record(accepted_by_block[block.id])
        for block in primaries
        if block.id in accepted_by_block
    ]
    issues: list[StageIssue] = []
    for batch_index, batch in enumerate(
        bounded_extraction_batches(prepared_items())
    ):
        batch_expected_ids = {item.block.id for item in batch}
        raw = _answer_batch_output(
            provider=provider,
            document=document,
            items=batch,
            batch_index=batch_index,
        )
        parsed = parse_answer_solution_extraction_output(raw)
        for issue in parsed.issues:
            issues.append(
                StageIssue(
                    stage='answer_solution_extraction',
                    code=issue.code,
                    block_id=_parse_issue_block_id(
                        issue,
                        batch_expected_ids,
                    ),
                    batch_index=batch_index,
                    retryable=True,
                )
            )

        returned_ids: set[int] = set()
        for record in parsed.records:
            if record.block_id not in batch_expected_ids:
                issues.append(
                    StageIssue(
                        stage='answer_solution_extraction',
                        code='unexpected_answer_solution_block_id',
                        block_id=record.block_id,
                        batch_index=batch_index,
                    )
                )
                continue
            returned_ids.add(record.block_id)
            proposals.append(record)

        for missing_id in sorted(batch_expected_ids - returned_ids):
            issues.append(
                StageIssue(
                    stage='answer_solution_extraction',
                    code='missing_answer_solution_block_id',
                    block_id=missing_id,
                    batch_index=batch_index,
                    retryable=True,
                )
            )

    if not proposals:
        raise ExtractionPipelineConfigurationError(
            'No valid answer-solution records were extracted.'
        )
    result = persist_answer_solution_records(
        document_id=document.id,
        expected_block_set_fingerprint=block_set.set_fingerprint,
        proposals=tuple(proposals),
    )
    return result, tuple(issues)


def run_document_extraction_pipeline(
    *,
    document_id: int,
    provider: ExamPrepV4ExtractionProvider | None = None,
) -> FullExtractionResult:
    """Run block detection, batched typed extraction, and exact matching."""

    document = ExamSourceDocument.objects.select_related('project').get(
        id=document_id
    )
    selected_provider = provider or StructuredLLMExamPrepV4Provider()

    block_set, block_issues = _detect_blocks(
        document=document,
        provider=selected_provider,
    )
    document.refresh_from_db()

    question_set, question_issues = _extract_questions(
        document=document,
        block_set=block_set,
        provider=selected_provider,
    )
    document.refresh_from_db()

    answer_set, answer_issues = _extract_answers(
        document=document,
        block_set=block_set,
        provider=selected_provider,
    )
    matches = build_deterministic_matches(project_id=document.project_id)

    return FullExtractionResult(
        document_id=document.id,
        project_id=document.project_id,
        block_set=block_set,
        question_set=question_set,
        answer_set=answer_set,
        matches=matches,
        issues=block_issues + question_issues + answer_issues,
        provider_calls=selected_provider.provider_calls,
    )
