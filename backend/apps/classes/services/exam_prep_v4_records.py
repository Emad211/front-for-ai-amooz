"""Typed per-block extraction persistence and deterministic matching for V4."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
import hashlib
import json
import re
import unicodedata
from typing import Any, Iterable, Mapping, Sequence

from django.db import transaction
from django.db.models import Max, Prefetch
from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from apps.classes.models_v4 import ExamProject, ExamSourceDocument
from apps.classes.models_v4_blocks import (
    ExamSourceBlock,
    ExamSourceBlockFragment,
    ExamSourceBlockKind,
)
from apps.classes.models_v4_records import (
    ExamAnswerSolutionRecord,
    ExamAnswerSolutionRecordEvidence,
    ExamExtractionLifecycle,
    ExamMatchDecision,
    ExamQuestionRecord,
    ExamQuestionRecordEvidence,
)
from apps.classes.services.exam_prep_v4_blocks import normalize_printed_number


RECORD_SCHEMA_VERSION = 1
MATCH_SCHEMA_VERSION = 1
_MAX_QUESTION_TEXT = 100_000
_MAX_OPTION_TEXT = 50_000
_MAX_FINAL_ANSWER = 20_000
_MAX_SOLUTION_TEXT = 250_000


class InvalidRecordInput(ValueError):
    pass


class StaleBlockSet(RuntimeError):
    pass


class RecordSetNotReady(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class QuestionOptionProposal:
    label: str
    text: str = ''


@dataclass(frozen=True, slots=True)
class QuestionRecordProposal:
    block_id: int
    question_text: str
    printed_number: str = ''
    section_key: str = ''
    options: tuple[QuestionOptionProposal, ...] = ()
    confidence: float = 0.0
    warnings: tuple[str, ...] = ()
    raw_payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AnswerSolutionRecordProposal:
    block_id: int
    printed_number: str = ''
    section_key: str = ''
    correct_option: str = ''
    final_answer: str = ''
    solution_text: str = ''
    confidence: float = 0.0
    warnings: tuple[str, ...] = ()
    raw_payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RecordParseIssue:
    code: str
    record_index: int | None = None
    block_id: int | None = None
    detail: str = ''

    def as_dict(self) -> dict[str, Any]:
        return {
            'code': self.code,
            'recordIndex': self.record_index,
            'blockId': self.block_id,
            'detail': self.detail,
        }


@dataclass(frozen=True, slots=True)
class QuestionParseResult:
    records: tuple[QuestionRecordProposal, ...]
    issues: tuple[RecordParseIssue, ...]


@dataclass(frozen=True, slots=True)
class AnswerParseResult:
    records: tuple[AnswerSolutionRecordProposal, ...]
    issues: tuple[RecordParseIssue, ...]


@dataclass(frozen=True, slots=True)
class PersistedRecordSet:
    document_id: int
    revision: int
    block_set_fingerprint: str
    set_fingerprint: str
    record_count: int
    evidence_link_count: int
    reused: bool = False


@dataclass(frozen=True, slots=True)
class PersistedMatchSet:
    project_id: int
    revision: int
    question_set_fingerprint: str
    answer_set_fingerprint: str
    set_fingerprint: str
    decision_count: int
    matched_count: int
    out_of_scope_count: int
    unresolved_count: int
    ambiguous_count: int
    conflict_count: int
    reused: bool = False


class QuestionOptionPayload(BaseModel):
    model_config = ConfigDict(extra='ignore', str_strip_whitespace=True)

    label: str = Field(min_length=1, max_length=32)
    text: str = Field(default='', max_length=_MAX_OPTION_TEXT)


class QuestionRecordPayload(BaseModel):
    model_config = ConfigDict(extra='ignore', populate_by_name=True, str_strip_whitespace=True)

    block_id: int = Field(alias='blockId', ge=1)
    printed_number: str = Field(default='', alias='printedNumber', max_length=64)
    section_key: str = Field(default='', alias='sectionKey', max_length=128)
    question_text: str = Field(alias='questionText', min_length=1, max_length=_MAX_QUESTION_TEXT)
    options: list[QuestionOptionPayload] = Field(default_factory=list, max_length=20)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list, max_length=50)

    @field_validator('warnings')
    @classmethod
    def bound_warnings(cls, values: list[str]) -> list[str]:
        return [str(value).strip()[:500] for value in values if str(value).strip()]


class AnswerSolutionRecordPayload(BaseModel):
    model_config = ConfigDict(extra='ignore', populate_by_name=True, str_strip_whitespace=True)

    block_id: int = Field(alias='blockId', ge=1)
    printed_number: str = Field(default='', alias='printedNumber', max_length=64)
    section_key: str = Field(default='', alias='sectionKey', max_length=128)
    correct_option: str = Field(default='', alias='correctOption', max_length=32)
    final_answer: str = Field(default='', alias='finalAnswer', max_length=_MAX_FINAL_ANSWER)
    solution_text: str = Field(default='', alias='solutionText', max_length=_MAX_SOLUTION_TEXT)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list, max_length=50)

    @field_validator('warnings')
    @classmethod
    def bound_warnings(cls, values: list[str]) -> list[str]:
        return [str(value).strip()[:500] for value in values if str(value).strip()]

    @model_validator(mode='after')
    def require_answer_content(self):
        if not (self.correct_option or self.final_answer or self.solution_text):
            raise ValueError('answer, final answer, or solution text is required')
        return self


def _records_from_payload(raw_output: Any, key: str) -> list[Any]:
    if isinstance(raw_output, list):
        return raw_output
    if isinstance(raw_output, dict) and isinstance(raw_output.get(key), list):
        return raw_output[key]
    raise InvalidRecordInput(
        f'Extraction output must be a list or an object with a {key} list.'
    )


def normalize_section_key(value: Any) -> str:
    normalized = unicodedata.normalize('NFKC', str(value or '')).strip().lower()
    return re.sub(r'\s+', ' ', normalized)[:128]


def normalize_option_label(value: Any) -> str:
    return normalize_printed_number(value).lower()[:32]


def _safe_raw_payload(parsed: BaseModel) -> dict[str, Any]:
    return parsed.model_dump(by_alias=True, mode='json')


def parse_question_extraction_output(raw_output: Any) -> QuestionParseResult:
    """Validate question records independently and keep valid siblings."""

    records = _records_from_payload(raw_output, 'questions')
    by_block: dict[int, QuestionRecordPayload] = {}
    issues: list[RecordParseIssue] = []
    for index, raw_record in enumerate(records):
        try:
            parsed = QuestionRecordPayload.model_validate(raw_record)
        except ValidationError as exc:
            issues.append(
                RecordParseIssue(
                    code='invalid_question_record',
                    record_index=index,
                    detail=str(exc.errors(include_url=False))[:1500],
                )
            )
            continue
        previous = by_block.get(parsed.block_id)
        if previous is not None:
            issues.append(
                RecordParseIssue(
                    code='duplicate_question_block',
                    record_index=index,
                    block_id=parsed.block_id,
                    detail='The higher-confidence record was retained.',
                )
            )
            if previous.confidence >= parsed.confidence:
                continue
        by_block[parsed.block_id] = parsed

    proposals = tuple(
        QuestionRecordProposal(
            block_id=parsed.block_id,
            printed_number=normalize_printed_number(parsed.printed_number),
            section_key=normalize_section_key(parsed.section_key),
            question_text=parsed.question_text.strip(),
            options=tuple(
                QuestionOptionProposal(
                    label=normalize_option_label(option.label),
                    text=option.text.strip(),
                )
                for option in parsed.options
            ),
            confidence=parsed.confidence,
            warnings=tuple(parsed.warnings),
            raw_payload=_safe_raw_payload(parsed),
        )
        for parsed in sorted(by_block.values(), key=lambda item: item.block_id)
    )
    return QuestionParseResult(records=proposals, issues=tuple(issues))


def parse_answer_solution_extraction_output(raw_output: Any) -> AnswerParseResult:
    """Validate unified answer-solution records independently."""

    records = _records_from_payload(raw_output, 'answers')
    by_block: dict[int, AnswerSolutionRecordPayload] = {}
    issues: list[RecordParseIssue] = []
    for index, raw_record in enumerate(records):
        try:
            parsed = AnswerSolutionRecordPayload.model_validate(raw_record)
        except ValidationError as exc:
            issues.append(
                RecordParseIssue(
                    code='invalid_answer_solution_record',
                    record_index=index,
                    detail=str(exc.errors(include_url=False))[:1500],
                )
            )
            continue
        previous = by_block.get(parsed.block_id)
        if previous is not None:
            issues.append(
                RecordParseIssue(
                    code='duplicate_answer_block',
                    record_index=index,
                    block_id=parsed.block_id,
                    detail='The higher-confidence record was retained.',
                )
            )
            if previous.confidence >= parsed.confidence:
                continue
        by_block[parsed.block_id] = parsed

    proposals = tuple(
        AnswerSolutionRecordProposal(
            block_id=parsed.block_id,
            printed_number=normalize_printed_number(parsed.printed_number),
            section_key=normalize_section_key(parsed.section_key),
            correct_option=normalize_option_label(parsed.correct_option),
            final_answer=parsed.final_answer.strip(),
            solution_text=parsed.solution_text.strip(),
            confidence=parsed.confidence,
            warnings=tuple(parsed.warnings),
            raw_payload=_safe_raw_payload(parsed),
        )
        for parsed in sorted(by_block.values(), key=lambda item: item.block_id)
    )
    return AnswerParseResult(records=proposals, issues=tuple(issues))


def _hash_payload(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(',', ':'),
        ).encode('utf-8')
    ).hexdigest()


def _current_block_set(document: ExamSourceDocument) -> tuple[ExamSourceBlock, ...]:
    revision = (
        ExamSourceBlock.objects.filter(
            document=document,
            source_map_fingerprint=document.source_map_fingerprint,
            status=ExamSourceBlock.Status.ACCEPTED,
        ).aggregate(value=Max('revision'))['value']
    )
    if revision is None:
        raise RecordSetNotReady('No accepted current source block set exists.')
    blocks = tuple(
        ExamSourceBlock.objects.filter(
            document=document,
            source_map_fingerprint=document.source_map_fingerprint,
            revision=revision,
            status=ExamSourceBlock.Status.ACCEPTED,
        )
        .select_related('segment', 'continuation_of')
        .order_by('order')
    )
    if not blocks:
        raise RecordSetNotReady('No accepted current source blocks exist.')
    set_fingerprints = {block.set_fingerprint for block in blocks}
    if len(set_fingerprints) != 1:
        raise RecordSetNotReady('Current source blocks do not share one set fingerprint.')
    return blocks


def _block_set_fingerprint(blocks: Sequence[ExamSourceBlock]) -> str:
    return blocks[0].set_fingerprint


def _validate_common_record(
    *,
    block: ExamSourceBlock,
    printed_number: str,
    section_key: str,
    confidence: float,
) -> tuple[str, str]:
    if not 0.0 <= float(confidence) <= 1.0:
        raise InvalidRecordInput('Record confidence must be between zero and one.')
    normalized_number = normalize_printed_number(printed_number)
    block_number = normalize_printed_number(block.printed_number)
    if normalized_number and block_number and normalized_number != block_number:
        raise InvalidRecordInput(
            f'Printed number conflicts with source block {block.id}.'
        )
    number = normalized_number or block_number
    section = normalize_section_key(section_key or block.segment.section_key)
    return number, section


def _question_payload(record: QuestionRecordProposal, block: ExamSourceBlock) -> dict[str, Any]:
    number, section = _validate_common_record(
        block=block,
        printed_number=record.printed_number,
        section_key=record.section_key,
        confidence=record.confidence,
    )
    text = record.question_text.strip()
    if not text:
        raise InvalidRecordInput('Question text may not be empty.')
    if len(text) > _MAX_QUESTION_TEXT:
        raise InvalidRecordInput('Question text exceeds the bounded record limit.')
    options: list[dict[str, str]] = []
    labels: set[str] = set()
    for option in record.options:
        label = normalize_option_label(option.label)
        if not label or label in labels:
            raise InvalidRecordInput('Question option labels must be non-empty and unique.')
        labels.add(label)
        option_text = option.text.strip()
        if len(option_text) > _MAX_OPTION_TEXT:
            raise InvalidRecordInput('Question option text exceeds the bounded record limit.')
        options.append({'label': label, 'text': option_text})
    return {
        'blockId': block.id,
        'blockFingerprint': block.fingerprint,
        'printedNumber': number,
        'sectionKey': section,
        'questionText': text,
        'options': options,
        'confidence': round(float(record.confidence), 6),
        'warnings': [str(value)[:500] for value in record.warnings][:50],
    }


def _answer_payload(
    record: AnswerSolutionRecordProposal,
    block: ExamSourceBlock,
) -> dict[str, Any]:
    number, section = _validate_common_record(
        block=block,
        printed_number=record.printed_number,
        section_key=record.section_key,
        confidence=record.confidence,
    )
    correct_option = normalize_option_label(record.correct_option)
    final_answer = record.final_answer.strip()
    solution_text = record.solution_text.strip()
    if block.kind == ExamSourceBlockKind.ANSWER_SOLUTION:
        if not solution_text:
            raise InvalidRecordInput(
                'Answer-solution blocks require the complete source solution text.'
            )
        if not (correct_option or final_answer):
            raise InvalidRecordInput(
                'Answer-solution blocks require a correct option or final answer.'
            )
    elif block.kind == ExamSourceBlockKind.ANSWER_KEY:
        if not (correct_option or final_answer):
            raise InvalidRecordInput('Answer-key blocks require an answer value.')
    elif block.kind == ExamSourceBlockKind.INLINE_QUESTION_ANSWER:
        if not (correct_option or final_answer or solution_text):
            raise InvalidRecordInput('Inline answer blocks require answer content.')
    if len(final_answer) > _MAX_FINAL_ANSWER:
        raise InvalidRecordInput('Final answer exceeds the bounded record limit.')
    if len(solution_text) > _MAX_SOLUTION_TEXT:
        raise InvalidRecordInput('Solution text exceeds the bounded record limit.')
    return {
        'blockId': block.id,
        'blockFingerprint': block.fingerprint,
        'printedNumber': number,
        'sectionKey': section,
        'correctOption': correct_option,
        'finalAnswer': final_answer,
        'solutionText': solution_text,
        'confidence': round(float(record.confidence), 6),
        'warnings': [str(value)[:500] for value in record.warnings][:50],
    }


def _question_set_fingerprint(
    payloads: Sequence[Mapping[str, Any]],
    *,
    block_set_fingerprint: str,
) -> str:
    return _hash_payload(
        {
            'schemaVersion': RECORD_SCHEMA_VERSION,
            'recordType': 'question',
            'blockSetFingerprint': block_set_fingerprint,
            'records': list(payloads),
        }
    )


def _answer_set_fingerprint(
    payloads: Sequence[Mapping[str, Any]],
    *,
    block_set_fingerprint: str,
) -> str:
    return _hash_payload(
        {
            'schemaVersion': RECORD_SCHEMA_VERSION,
            'recordType': 'answer_solution',
            'blockSetFingerprint': block_set_fingerprint,
            'records': list(payloads),
        }
    )


def _question_record_fingerprint(payload: Mapping[str, Any]) -> str:
    return _hash_payload(
        {
            'schemaVersion': RECORD_SCHEMA_VERSION,
            'recordType': 'question',
            'record': payload,
        }
    )


def _answer_record_fingerprint(payload: Mapping[str, Any]) -> str:
    return _hash_payload(
        {
            'schemaVersion': RECORD_SCHEMA_VERSION,
            'recordType': 'answer_solution',
            'record': payload,
        }
    )


def _current_question_records(document: ExamSourceDocument) -> tuple[ExamQuestionRecord, ...]:
    return tuple(
        ExamQuestionRecord.objects.filter(
            document=document,
            lifecycle_status=ExamExtractionLifecycle.ACCEPTED,
        ).order_by('order')
    )


def _current_answer_records(
    document: ExamSourceDocument,
) -> tuple[ExamAnswerSolutionRecord, ...]:
    return tuple(
        ExamAnswerSolutionRecord.objects.filter(
            document=document,
            lifecycle_status=ExamExtractionLifecycle.ACCEPTED,
        ).order_by('order')
    )


def _next_revision(model, *, document: ExamSourceDocument) -> int:
    return (model.objects.filter(document=document).aggregate(value=Max('revision'))['value'] or 0) + 1


def _continuation_chain(
    primary: ExamSourceBlock,
    blocks: Sequence[ExamSourceBlock],
) -> tuple[ExamSourceBlock, ...]:
    children: dict[int, list[ExamSourceBlock]] = defaultdict(list)
    for block in blocks:
        if block.continuation_of_id:
            children[block.continuation_of_id].append(block)
    for values in children.values():
        values.sort(key=lambda item: item.order)

    result: list[ExamSourceBlock] = []
    seen: set[int] = set()

    def visit(block: ExamSourceBlock) -> None:
        if block.id in seen:
            raise InvalidRecordInput('Continuation evidence contains a cycle.')
        seen.add(block.id)
        result.append(block)
        for child in children.get(block.id, []):
            visit(child)

    visit(primary)
    return tuple(result)


@transaction.atomic
def persist_question_records(
    *,
    document_id: int,
    expected_block_set_fingerprint: str,
    proposals: Iterable[QuestionRecordProposal],
) -> PersistedRecordSet:
    document = (
        ExamSourceDocument.objects.select_for_update()
        .select_related('project')
        .get(id=document_id)
    )
    project = ExamProject.objects.select_for_update().get(id=document.project_id)
    blocks = _current_block_set(document)
    block_set_fingerprint = _block_set_fingerprint(blocks)
    if block_set_fingerprint != expected_block_set_fingerprint:
        raise StaleBlockSet('The source block set changed before question persistence.')
    blocks_by_id = {block.id: block for block in blocks}

    records = tuple(proposals)
    seen: set[int] = set()
    normalized: list[tuple[QuestionRecordProposal, ExamSourceBlock, dict[str, Any]]] = []
    for record in records:
        if record.block_id in seen:
            raise InvalidRecordInput('Only one question record per source block is allowed.')
        seen.add(record.block_id)
        block = blocks_by_id.get(record.block_id)
        if block is None:
            raise InvalidRecordInput('Question record references a stale source block.')
        if block.kind not in {
            ExamSourceBlockKind.QUESTION,
            ExamSourceBlockKind.INLINE_QUESTION_ANSWER,
        }:
            raise InvalidRecordInput('Question records require a question-bearing block.')
        normalized.append((record, block, _question_payload(record, block)))
    normalized.sort(key=lambda item: item[1].order)
    payloads = [payload for _record, _block, payload in normalized]
    set_fingerprint = _question_set_fingerprint(
        payloads,
        block_set_fingerprint=block_set_fingerprint,
    )

    current = _current_question_records(document)
    if current and all(item.set_fingerprint == set_fingerprint for item in current):
        return PersistedRecordSet(
            document_id=document.id,
            revision=current[0].revision,
            block_set_fingerprint=block_set_fingerprint,
            set_fingerprint=set_fingerprint,
            record_count=len(current),
            evidence_link_count=sum(item.evidence_links.count() for item in current),
            reused=True,
        )
    if current:
        ExamQuestionRecord.objects.filter(id__in=[item.id for item in current]).update(
            lifecycle_status=ExamExtractionLifecycle.SUPERSEDED,
        )
    revision = _next_revision(ExamQuestionRecord, document=document)
    evidence: list[ExamQuestionRecordEvidence] = []
    for order, (proposal, block, payload) in enumerate(normalized):
        record = ExamQuestionRecord.objects.create(
            project=project,
            document=document,
            source_block=block,
            revision=revision,
            order=order,
            section_key=payload['sectionKey'],
            printed_number=payload['printedNumber'],
            question_text=payload['questionText'],
            options=payload['options'],
            confidence=Decimal(str(payload['confidence'])),
            block_set_fingerprint=block_set_fingerprint,
            set_fingerprint=set_fingerprint,
            fingerprint=_question_record_fingerprint(payload),
            warnings=payload['warnings'],
            raw_payload=dict(proposal.raw_payload),
        )
        evidence.append(
            ExamQuestionRecordEvidence(record=record, block=block, order=0)
        )
    ExamQuestionRecordEvidence.objects.bulk_create(evidence)

    project.status = ExamProject.Status.EXTRACTING_ANSWERS
    project.workflow_state = {
        'stage': 'questions_ready',
        'progressPercent': 50,
        'questionCount': len(normalized),
    }
    project.error_code = ''
    project.error_detail = ''
    project.save(
        update_fields=[
            'status',
            'workflow_state',
            'error_code',
            'error_detail',
            'updated_at',
        ]
    )
    return PersistedRecordSet(
        document_id=document.id,
        revision=revision,
        block_set_fingerprint=block_set_fingerprint,
        set_fingerprint=set_fingerprint,
        record_count=len(normalized),
        evidence_link_count=len(evidence),
        reused=False,
    )


@transaction.atomic
def persist_answer_solution_records(
    *,
    document_id: int,
    expected_block_set_fingerprint: str,
    proposals: Iterable[AnswerSolutionRecordProposal],
) -> PersistedRecordSet:
    document = (
        ExamSourceDocument.objects.select_for_update()
        .select_related('project')
        .get(id=document_id)
    )
    project = ExamProject.objects.select_for_update().get(id=document.project_id)
    blocks = _current_block_set(document)
    block_set_fingerprint = _block_set_fingerprint(blocks)
    if block_set_fingerprint != expected_block_set_fingerprint:
        raise StaleBlockSet('The source block set changed before answer persistence.')
    blocks_by_id = {block.id: block for block in blocks}

    records = tuple(proposals)
    seen: set[int] = set()
    normalized: list[
        tuple[
            AnswerSolutionRecordProposal,
            ExamSourceBlock,
            tuple[ExamSourceBlock, ...],
            dict[str, Any],
        ]
    ] = []
    for record in records:
        if record.block_id in seen:
            raise InvalidRecordInput('Only one answer record per source block is allowed.')
        seen.add(record.block_id)
        block = blocks_by_id.get(record.block_id)
        if block is None:
            raise InvalidRecordInput('Answer record references a stale source block.')
        if block.kind not in {
            ExamSourceBlockKind.ANSWER_SOLUTION,
            ExamSourceBlockKind.ANSWER_KEY,
            ExamSourceBlockKind.INLINE_QUESTION_ANSWER,
        }:
            raise InvalidRecordInput('Answer records require an answer-bearing primary block.')
        chain = _continuation_chain(block, blocks)
        normalized.append((record, block, chain, _answer_payload(record, block)))
    normalized.sort(key=lambda item: item[1].order)
    payloads = [
        {
            **payload,
            'evidenceBlockFingerprints': [item.fingerprint for item in chain],
        }
        for _record, _block, chain, payload in normalized
    ]
    set_fingerprint = _answer_set_fingerprint(
        payloads,
        block_set_fingerprint=block_set_fingerprint,
    )

    current = _current_answer_records(document)
    if current and all(item.set_fingerprint == set_fingerprint for item in current):
        return PersistedRecordSet(
            document_id=document.id,
            revision=current[0].revision,
            block_set_fingerprint=block_set_fingerprint,
            set_fingerprint=set_fingerprint,
            record_count=len(current),
            evidence_link_count=sum(item.evidence_links.count() for item in current),
            reused=True,
        )
    if current:
        ExamAnswerSolutionRecord.objects.filter(id__in=[item.id for item in current]).update(
            lifecycle_status=ExamExtractionLifecycle.SUPERSEDED,
        )
    revision = _next_revision(ExamAnswerSolutionRecord, document=document)
    evidence: list[ExamAnswerSolutionRecordEvidence] = []
    for order, (proposal, block, chain, payload) in enumerate(normalized):
        fingerprint_payload = {
            **payload,
            'evidenceBlockFingerprints': [item.fingerprint for item in chain],
        }
        record = ExamAnswerSolutionRecord.objects.create(
            project=project,
            document=document,
            source_block=block,
            revision=revision,
            order=order,
            section_key=payload['sectionKey'],
            printed_number=payload['printedNumber'],
            correct_option=payload['correctOption'],
            final_answer=payload['finalAnswer'],
            solution_text=payload['solutionText'],
            confidence=Decimal(str(payload['confidence'])),
            block_set_fingerprint=block_set_fingerprint,
            set_fingerprint=set_fingerprint,
            fingerprint=_answer_record_fingerprint(fingerprint_payload),
            warnings=payload['warnings'],
            raw_payload=dict(proposal.raw_payload),
        )
        for evidence_order, evidence_block in enumerate(chain):
            evidence.append(
                ExamAnswerSolutionRecordEvidence(
                    record=record,
                    block=evidence_block,
                    order=evidence_order,
                )
            )
    ExamAnswerSolutionRecordEvidence.objects.bulk_create(evidence)

    project.status = ExamProject.Status.MATCHING
    project.workflow_state = {
        'stage': 'answers_ready',
        'progressPercent': 65,
        'answerSolutionCount': len(normalized),
    }
    project.error_code = ''
    project.error_detail = ''
    project.save(
        update_fields=[
            'status',
            'workflow_state',
            'error_code',
            'error_detail',
            'updated_at',
        ]
    )
    return PersistedRecordSet(
        document_id=document.id,
        revision=revision,
        block_set_fingerprint=block_set_fingerprint,
        set_fingerprint=set_fingerprint,
        record_count=len(normalized),
        evidence_link_count=len(evidence),
        reused=False,
    )


def _current_project_questions(project: ExamProject) -> tuple[ExamQuestionRecord, ...]:
    return tuple(
        ExamQuestionRecord.objects.filter(
            project=project,
            lifecycle_status=ExamExtractionLifecycle.ACCEPTED,
        )
        .select_related('document', 'source_block')
        .order_by('document__upload_order', 'order', 'id')
    )


def _current_project_answers(
    project: ExamProject,
) -> tuple[ExamAnswerSolutionRecord, ...]:
    return tuple(
        ExamAnswerSolutionRecord.objects.filter(
            project=project,
            lifecycle_status=ExamExtractionLifecycle.ACCEPTED,
        )
        .select_related('document', 'source_block')
        .order_by('document__upload_order', 'order', 'id')
    )


def _record_set_fingerprint(records: Sequence[Any], record_type: str) -> str:
    return _hash_payload(
        {
            'schemaVersion': RECORD_SCHEMA_VERSION,
            'recordType': record_type,
            'records': [record.fingerprint for record in records],
        }
    )


def _question_option_labels(question: ExamQuestionRecord) -> set[str]:
    labels: set[str] = set()
    if not isinstance(question.options, list):
        return labels
    for option in question.options:
        if isinstance(option, dict):
            label = normalize_option_label(option.get('label'))
            if label:
                labels.add(label)
    return labels


def _decision_payload(
    *,
    answer: ExamAnswerSolutionRecord,
    question: ExamQuestionRecord | None,
    decision: str,
    method: str,
    reason_code: str,
    normalized_section: str,
    normalized_number: str,
) -> dict[str, Any]:
    return {
        'answerFingerprint': answer.fingerprint,
        'questionFingerprint': question.fingerprint if question else None,
        'decision': decision,
        'method': method,
        'reasonCode': reason_code,
        'normalizedSection': normalized_section,
        'normalizedNumber': normalized_number,
    }


@transaction.atomic
def build_deterministic_matches(*, project_id: int) -> PersistedMatchSet:
    """Rebuild exact project-scoped answer decisions without fuzzy matching."""

    project = ExamProject.objects.select_for_update().get(id=project_id)
    questions = _current_project_questions(project)
    answers = _current_project_answers(project)
    if not questions:
        raise RecordSetNotReady('No accepted question inventory exists.')
    if not answers:
        raise RecordSetNotReady('No accepted answer-solution records exist.')

    question_set_fingerprint = _record_set_fingerprint(questions, 'question')
    answer_set_fingerprint = _record_set_fingerprint(answers, 'answer_solution')

    by_scope_number: dict[tuple[str, str], list[ExamQuestionRecord]] = defaultdict(list)
    by_number: dict[str, list[ExamQuestionRecord]] = defaultdict(list)
    for question in questions:
        number = normalize_printed_number(question.printed_number)
        section = normalize_section_key(question.section_key)
        if number:
            by_scope_number[(section, number)].append(question)
            by_number[number].append(question)

    decisions: list[
        tuple[
            ExamAnswerSolutionRecord,
            ExamQuestionRecord | None,
            str,
            str,
            str,
            str,
            str,
            dict[str, Any],
        ]
    ] = []
    for answer in answers:
        number = normalize_printed_number(answer.printed_number)
        section = normalize_section_key(answer.section_key)
        question: ExamQuestionRecord | None = None
        decision = ExamMatchDecision.Decision.UNRESOLVED
        method = ExamMatchDecision.Method.NONE
        reason_code = 'missing_printed_number'
        metadata: dict[str, Any] = {}

        if number:
            exact = by_scope_number.get((section, number), [])
            if len(exact) == 1:
                question = exact[0]
                decision = ExamMatchDecision.Decision.MATCHED
                method = ExamMatchDecision.Method.EXACT_SCOPE_NUMBER
                reason_code = 'exact_scope_number'
            elif len(exact) > 1:
                decision = ExamMatchDecision.Decision.AMBIGUOUS
                reason_code = 'duplicate_scope_number'
                metadata['candidateCount'] = len(exact)
            else:
                candidates = by_number.get(number, [])
                if len(candidates) == 1:
                    question = candidates[0]
                    decision = ExamMatchDecision.Decision.MATCHED
                    method = ExamMatchDecision.Method.UNIQUE_NUMBER
                    reason_code = 'unique_project_number'
                elif len(candidates) > 1:
                    decision = ExamMatchDecision.Decision.AMBIGUOUS
                    reason_code = 'duplicate_project_number'
                    metadata['candidateCount'] = len(candidates)
                else:
                    decision = ExamMatchDecision.Decision.OUT_OF_SCOPE
                    reason_code = 'number_not_in_question_inventory'

        if question is not None and answer.correct_option:
            option_labels = _question_option_labels(question)
            if option_labels and normalize_option_label(answer.correct_option) not in option_labels:
                question = None
                decision = ExamMatchDecision.Decision.CONFLICT
                method = ExamMatchDecision.Method.NONE
                reason_code = 'correct_option_not_in_question_options'
                metadata['availableOptionCount'] = len(option_labels)

        decisions.append(
            (
                answer,
                question,
                decision,
                method,
                reason_code,
                section,
                number,
                metadata,
            )
        )

    decision_payloads = [
        _decision_payload(
            answer=answer,
            question=question,
            decision=decision,
            method=method,
            reason_code=reason_code,
            normalized_section=section,
            normalized_number=number,
        )
        for answer, question, decision, method, reason_code, section, number, _metadata in decisions
    ]
    set_fingerprint = _hash_payload(
        {
            'schemaVersion': MATCH_SCHEMA_VERSION,
            'questionSetFingerprint': question_set_fingerprint,
            'answerSetFingerprint': answer_set_fingerprint,
            'decisions': decision_payloads,
        }
    )

    current = tuple(
        ExamMatchDecision.objects.filter(
            project=project,
            lifecycle_status=ExamExtractionLifecycle.ACCEPTED,
        ).order_by('order')
    )
    if current and all(item.set_fingerprint == set_fingerprint for item in current):
        counts = defaultdict(int)
        for item in current:
            counts[item.decision] += 1
        return PersistedMatchSet(
            project_id=project.id,
            revision=current[0].revision,
            question_set_fingerprint=question_set_fingerprint,
            answer_set_fingerprint=answer_set_fingerprint,
            set_fingerprint=set_fingerprint,
            decision_count=len(current),
            matched_count=counts[ExamMatchDecision.Decision.MATCHED],
            out_of_scope_count=counts[ExamMatchDecision.Decision.OUT_OF_SCOPE],
            unresolved_count=counts[ExamMatchDecision.Decision.UNRESOLVED],
            ambiguous_count=counts[ExamMatchDecision.Decision.AMBIGUOUS],
            conflict_count=counts[ExamMatchDecision.Decision.CONFLICT],
            reused=True,
        )
    if current:
        ExamMatchDecision.objects.filter(id__in=[item.id for item in current]).update(
            lifecycle_status=ExamExtractionLifecycle.SUPERSEDED,
        )
    revision = (
        ExamMatchDecision.objects.filter(project=project).aggregate(value=Max('revision'))[
            'value'
        ]
        or 0
    ) + 1

    created: list[ExamMatchDecision] = []
    for order, (
        answer,
        question,
        decision,
        method,
        reason_code,
        section,
        number,
        metadata,
    ) in enumerate(decisions):
        payload = decision_payloads[order]
        created.append(
            ExamMatchDecision.objects.create(
                project=project,
                answer_record=answer,
                question_record=question,
                revision=revision,
                order=order,
                decision=decision,
                method=method,
                normalized_section=section,
                normalized_number=number,
                reason_code=reason_code,
                question_set_fingerprint=question_set_fingerprint,
                answer_set_fingerprint=answer_set_fingerprint,
                set_fingerprint=set_fingerprint,
                fingerprint=_hash_payload(
                    {
                        'schemaVersion': MATCH_SCHEMA_VERSION,
                        'decision': payload,
                    }
                ),
                metadata=metadata,
            )
        )

    counts = defaultdict(int)
    for item in created:
        counts[item.decision] += 1
    issue_count = len(created) - counts[ExamMatchDecision.Decision.MATCHED]
    project.status = ExamProject.Status.AWAITING_REVIEW
    project.workflow_state = {
        'stage': 'matching_complete',
        'progressPercent': 80,
        'questionCount': len(questions),
        'answerSolutionCount': len(answers),
        'matchedCount': counts[ExamMatchDecision.Decision.MATCHED],
        'outOfScopeCount': counts[ExamMatchDecision.Decision.OUT_OF_SCOPE],
        'unresolvedCount': counts[ExamMatchDecision.Decision.UNRESOLVED],
        'ambiguousCount': counts[ExamMatchDecision.Decision.AMBIGUOUS],
        'conflictCount': counts[ExamMatchDecision.Decision.CONFLICT],
        'warningCount': issue_count,
    }
    project.error_code = ''
    project.error_detail = ''
    project.save(
        update_fields=[
            'status',
            'workflow_state',
            'error_code',
            'error_detail',
            'updated_at',
        ]
    )
    return PersistedMatchSet(
        project_id=project.id,
        revision=revision,
        question_set_fingerprint=question_set_fingerprint,
        answer_set_fingerprint=answer_set_fingerprint,
        set_fingerprint=set_fingerprint,
        decision_count=len(created),
        matched_count=counts[ExamMatchDecision.Decision.MATCHED],
        out_of_scope_count=counts[ExamMatchDecision.Decision.OUT_OF_SCOPE],
        unresolved_count=counts[ExamMatchDecision.Decision.UNRESOLVED],
        ambiguous_count=counts[ExamMatchDecision.Decision.AMBIGUOUS],
        conflict_count=counts[ExamMatchDecision.Decision.CONFLICT],
        reused=False,
    )


def get_teacher_record_summary(*, teacher, project_id: int) -> dict[str, Any]:
    """Content-free owner-scoped semantic pipeline summary."""

    project = ExamProject.objects.filter(id=project_id, teacher=teacher).first()
    if project is None:
        raise ExamProject.DoesNotExist
    questions = _current_project_questions(project)
    answers = _current_project_answers(project)
    decisions = tuple(
        ExamMatchDecision.objects.filter(
            project=project,
            lifecycle_status=ExamExtractionLifecycle.ACCEPTED,
        )
        .select_related('answer_record', 'question_record')
        .order_by('order')
    )
    counts = defaultdict(int)
    for decision in decisions:
        counts[decision.decision] += 1
    return {
        'projectId': project.id,
        'questionCount': len(questions),
        'answerSolutionCount': len(answers),
        'decisionCount': len(decisions),
        'matchedCount': counts[ExamMatchDecision.Decision.MATCHED],
        'outOfScopeCount': counts[ExamMatchDecision.Decision.OUT_OF_SCOPE],
        'unresolvedCount': counts[ExamMatchDecision.Decision.UNRESOLVED],
        'ambiguousCount': counts[ExamMatchDecision.Decision.AMBIGUOUS],
        'conflictCount': counts[ExamMatchDecision.Decision.CONFLICT],
        'decisions': [
            {
                'order': decision.order,
                'decision': decision.decision,
                'method': decision.method,
                'printedNumber': decision.normalized_number or None,
                'sectionKey': decision.normalized_section or None,
                'reasonCode': decision.reason_code,
                'questionRecordId': decision.question_record_id,
                'answerSolutionRecordId': decision.answer_record_id,
            }
            for decision in decisions
        ],
    }
