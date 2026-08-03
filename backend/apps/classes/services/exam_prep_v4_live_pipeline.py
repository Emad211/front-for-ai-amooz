"""Provider-neutral full semantic extraction runner for Exam Prep V4.

The fake and live providers use the same persistence path. The provider may only
propose structure/content; confirmed source scope, block kind, evidence identity,
revisions, fingerprints, and automatic matching remain server-authoritative.
"""
from __future__ import annotations

from dataclasses import dataclass
import io
import os
from typing import Any, Protocol, Sequence

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
    BlockParseIssue,
    PersistedBlockSet,
    SourceBlockProposal,
    parse_block_detector_output,
    persist_source_blocks,
)
from apps.classes.services.exam_prep_v4_records import (
    AnswerSolutionRecordProposal,
    PersistedMatchSet,
    PersistedRecordSet,
    QuestionRecordProposal,
    RecordParseIssue,
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
QUESTION_PROMPT_VERSION = 'exam-prep-v4-question-extraction-v1'
ANSWER_PROMPT_VERSION = 'exam-prep-v4-answer-solution-extraction-v1'


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
class StageIssue:
    stage: str
    code: str
    block_id: int | None = None
    segment_order: int | None = None


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
    max_bytes = _positive_int_env('EXAM_PREP_V4_VISION_IMAGE_MAX_BYTES', 4 * 1024 * 1024)
    if len(data) > max_bytes:
        raise ExtractionImageError('Prepared vision image exceeds the bounded byte limit.')
    return data


def prepare_full_page_image(page: ExamSourcePage) -> PreparedVisionImage:
    image = _open_oriented_page(page)
    data = _encode_bounded_jpeg(
        image,
        max_dimension=_positive_int_env('EXAM_PREP_V4_BLOCK_PAGE_MAX_DIMENSION', 1600),
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


def _vision_content(prefix: str, images: Sequence[PreparedVisionImage]) -> list[Any]:
    content: list[Any] = [{'type': 'text', 'text': prefix}]
    for image in images:
        content.append({'type': 'text', 'text': image.label})
        content.append(part_from_bytes(data=image.image, mime_type=image.mime_type))
    return content


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
        self.question_model = _select_model(question_model, 'EXAM_PREP_V4_QUESTION_MODEL')
        self.answer_model = _select_model(answer_model, 'EXAM_PREP_V4_ANSWER_MODEL')
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
            timeout=_positive_float_env('EXAM_PREP_V4_EXTRACTION_TIMEOUT_SECONDS', 180.0),
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
            f'{{"segmentOrder":{segment.order},"role":"{segment.role}",'
            f'"pageNumbers":[{",".join(str(page.page_number) for page in pages)}]}}'
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

    def extract_question(
        self,
        *,
        document: ExamSourceDocument,
        block: ExamSourceBlock,
        images: Sequence[PreparedVisionImage],
    ) -> Any:
        prefix = (
            'AUTHORITATIVE_BLOCK_JSON:\n'
            f'{{"blockId":{block.id},"kind":"{block.kind}",'
            f'"printedNumber":"{block.printed_number}",'
            f'"sectionKey":"{block.segment.section_key}"}}'
        )
        envelope = self._generate(
            schema=QuestionExtractionEnvelope,
            prompt_key='exam_prep_v4_question_extraction',
            content=_vision_content(prefix, images),
            model=self.question_model,
            detail='exam_prep_v4_question_extraction',
            document=document,
            tracking={
                'stage': 'question_extraction',
                'source_block_id': block.id,
                'block_fingerprint': block.fingerprint,
                'prompt_version': QUESTION_PROMPT_VERSION,
            },
            max_output_tokens=8_000,
        )
        return {'questions': envelope.questions}

    def extract_answer_solution(
        self,
        *,
        document: ExamSourceDocument,
        block: ExamSourceBlock,
        evidence_blocks: Sequence[ExamSourceBlock],
        images: Sequence[PreparedVisionImage],
    ) -> Any:
        prefix = (
            'AUTHORITATIVE_BLOCK_JSON:\n'
            f'{{"blockId":{block.id},"kind":"{block.kind}",'
            f'"printedNumber":"{block.printed_number}",'
            f'"sectionKey":"{block.segment.section_key}",'
            f'"evidenceBlockOrders":[{",".join(str(item.order) for item in evidence_blocks)}]}}'
        )
        envelope = self._generate(
            schema=AnswerExtractionEnvelope,
            prompt_key='exam_prep_v4_answer_solution_extraction',
            content=_vision_content(prefix, images),
            model=self.answer_model,
            detail='exam_prep_v4_answer_solution_extraction',
            document=document,
            tracking={
                'stage': 'answer_solution_extraction',
                'source_block_id': block.id,
                'block_fingerprint': block.fingerprint,
                'prompt_version': ANSWER_PROMPT_VERSION,
            },
            max_output_tokens=16_000,
        )
        return {'answers': envelope.answers}


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
    by_number = {page.page_number: index for index, page in enumerate(ordered_pages)}
    start = by_number[segment.start_page]
    end = by_number[segment.end_page]
    low, high = sorted((start, end))
    sequence = tuple(page.page_number for page in ordered_pages[low : high + 1])
    return sequence if start <= end else tuple(reversed(sequence))


def _current_confirmed_scope(document: ExamSourceDocument):
    if not (
        document.status == ExamSourceDocument.Status.CONFIRMED
        and document.teacher_confirmed_revision == document.classification_revision
        and document.teacher_confirmed_fingerprint == document.source_map_fingerprint
        and document.teacher_confirmed_at is not None
    ):
        raise ExtractionPipelineConfigurationError(
            'The exact current Source Map must be teacher-confirmed first.'
        )
    pages = tuple(
        ExamSourcePage.objects.filter(document=document).order_by(
            'display_order', 'page_number'
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
        raise ExtractionPipelineConfigurationError('Confirmed Source Map is incomplete.')
    return pages, segments


def _existing_current_blocks(document: ExamSourceDocument) -> tuple[ExamSourceBlock, ...]:
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


def _block_set_result(blocks: Sequence[ExamSourceBlock]) -> PersistedBlockSet:
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
        images = tuple(prepare_full_page_image(page) for page in segment_pages)
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
            current_proposal = global_proposals[start_index + index]
            global_proposals[start_index + index] = SourceBlockProposal(
                order=current_proposal.order,
                segment_order=current_proposal.segment_order,
                kind=current_proposal.kind,
                fragments=current_proposal.fragments,
                printed_number=current_proposal.printed_number,
                confidence=current_proposal.confidence,
                continuation_of_order=parent,
                metadata=current_proposal.metadata,
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


def _current_question_set(document: ExamSourceDocument, block_fingerprint: str):
    records = tuple(
        ExamQuestionRecord.objects.filter(
            document=document,
            block_set_fingerprint=block_fingerprint,
            lifecycle_status=ExamExtractionLifecycle.ACCEPTED,
            source_block__status=ExamSourceBlock.Status.ACCEPTED,
        ).order_by('order')
    )
    if not records:
        return None
    return PersistedRecordSet(
        document_id=document.id,
        revision=records[0].revision,
        block_set_fingerprint=block_fingerprint,
        set_fingerprint=records[0].set_fingerprint,
        record_count=len(records),
        evidence_link_count=sum(record.evidence_links.count() for record in records),
        reused=True,
    )


def _current_answer_set(document: ExamSourceDocument, block_fingerprint: str):
    records = tuple(
        ExamAnswerSolutionRecord.objects.filter(
            document=document,
            block_set_fingerprint=block_fingerprint,
            lifecycle_status=ExamExtractionLifecycle.ACCEPTED,
            source_block__status=ExamSourceBlock.Status.ACCEPTED,
        ).order_by('order')
    )
    if not records:
        return None
    return PersistedRecordSet(
        document_id=document.id,
        revision=records[0].revision,
        block_set_fingerprint=block_fingerprint,
        set_fingerprint=records[0].set_fingerprint,
        record_count=len(records),
        evidence_link_count=sum(record.evidence_links.count() for record in records),
        reused=True,
    )


def _extract_questions(
    *,
    document: ExamSourceDocument,
    block_set: PersistedBlockSet,
    provider: ExamPrepV4ExtractionProvider,
) -> tuple[PersistedRecordSet, tuple[StageIssue, ...]]:
    existing = _current_question_set(document, block_set.set_fingerprint)
    if existing:
        return existing, ()
    blocks = tuple(
        ExamSourceBlock.objects.filter(
            document=document,
            revision=block_set.revision,
            set_fingerprint=block_set.set_fingerprint,
            status=ExamSourceBlock.Status.ACCEPTED,
            kind__in=[
                ExamSourceBlockKind.QUESTION,
                ExamSourceBlockKind.INLINE_QUESTION_ANSWER,
            ],
        ).select_related('segment').order_by('order')
    )
    proposals: list[QuestionRecordProposal] = []
    issues: list[StageIssue] = []
    for block in blocks:
        images = prepare_block_crop_images(block)
        raw = provider.extract_question(
            document=document,
            block=block,
            images=images,
        )
        parsed = parse_question_extraction_output(raw)
        matching = [record for record in parsed.records if record.block_id == block.id]
        for issue in parsed.issues:
            issues.append(
                StageIssue(
                    stage='question_extraction',
                    code=issue.code,
                    block_id=block.id,
                )
            )
        if len(matching) != 1:
            issues.append(
                StageIssue(
                    stage='question_extraction',
                    code='missing_or_duplicate_question_record',
                    block_id=block.id,
                )
            )
            continue
        proposals.append(matching[0])
    if not proposals:
        raise ExtractionPipelineConfigurationError('No valid question records were extracted.')
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

    def add(block: ExamSourceBlock) -> None:
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
    existing = _current_answer_set(document, block_set.set_fingerprint)
    if existing:
        return existing, ()
    all_blocks = tuple(
        ExamSourceBlock.objects.filter(
            document=document,
            revision=block_set.revision,
            set_fingerprint=block_set.set_fingerprint,
            status=ExamSourceBlock.Status.ACCEPTED,
        ).select_related('segment', 'continuation_of').order_by('order')
    )
    primaries = tuple(
        block
        for block in all_blocks
        if block.kind in {
            ExamSourceBlockKind.ANSWER_SOLUTION,
            ExamSourceBlockKind.ANSWER_KEY,
            ExamSourceBlockKind.INLINE_QUESTION_ANSWER,
        }
    )
    proposals: list[AnswerSolutionRecordProposal] = []
    issues: list[StageIssue] = []
    for block in primaries:
        chain = _continuation_chain(block, all_blocks)
        images = prepare_block_crop_images(block, evidence_blocks=chain)
        raw = provider.extract_answer_solution(
            document=document,
            block=block,
            evidence_blocks=chain,
            images=images,
        )
        parsed = parse_answer_solution_extraction_output(raw)
        matching = [record for record in parsed.records if record.block_id == block.id]
        for issue in parsed.issues:
            issues.append(
                StageIssue(
                    stage='answer_solution_extraction',
                    code=issue.code,
                    block_id=block.id,
                )
            )
        if len(matching) != 1:
            issues.append(
                StageIssue(
                    stage='answer_solution_extraction',
                    code='missing_or_duplicate_answer_solution_record',
                    block_id=block.id,
                )
            )
            continue
        proposals.append(matching[0])
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
    """Run block detection, typed extraction, and exact matching for one PDF."""

    document = ExamSourceDocument.objects.select_related('project').get(id=document_id)
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
