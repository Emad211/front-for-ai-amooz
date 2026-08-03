"""Content-free production observability for Exam Prep V4 extraction.

All events are correlation-friendly JSON messages. This module intentionally
accepts only explicit safe identifiers, counts, timings, model names and reason
codes; source text, OCR/model payloads, prompts, filenames and object keys must
never be passed to it.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import re
import time
import uuid
from typing import Any, Callable, Mapping, Sequence

from django.utils import timezone

from apps.classes.models_v4 import ExamProject


LOGGER = logging.getLogger('apps.classes.exam_prep_v4')
_SAFE_CODE = re.compile(r'^[A-Za-z0-9_.:-]{1,160}$')


@dataclass(frozen=True, slots=True)
class ExtractionRunContext:
    run_id: str
    task_id: str
    project_id: int
    document_id: int
    source_map_revision: int
    source_map_fingerprint: str
    attempt: int = 1

    @property
    def fingerprint_prefix(self) -> str:
        return str(self.source_map_fingerprint or '')[:12]

    def fields(self) -> dict[str, Any]:
        return {
            'runId': self.run_id,
            'taskId': self.task_id,
            'projectId': self.project_id,
            'documentId': self.document_id,
            'sourceMapRevision': self.source_map_revision,
            'sourceMapFingerprintPrefix': self.fingerprint_prefix,
            'attempt': self.attempt,
        }


def new_extraction_run_id() -> str:
    return str(uuid.uuid4())


def _safe_scalar(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    rendered = str(value).strip()
    if not rendered:
        return None
    return rendered[:240] if _SAFE_CODE.fullmatch(rendered[:240]) else 'redacted'


def _safe_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key)[:80]: _safe_value(nested)
            for key, nested in value.items()
            if _SAFE_CODE.fullmatch(str(key)[:80])
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_safe_value(item) for item in list(value)[:100]]
    return _safe_scalar(value)


def emit_v4_event(
    event: str,
    *,
    context: ExtractionRunContext | None = None,
    level: int = logging.INFO,
    **fields: Any,
) -> None:
    payload: dict[str, Any] = {
        'event': str(event)[:160],
        'timestamp': timezone.now().isoformat(),
    }
    if context is not None:
        payload.update(context.fields())
    payload.update(
        {
            key: _safe_value(value)
            for key, value in fields.items()
            if value is not None and _SAFE_CODE.fullmatch(str(key)[:80])
        }
    )
    LOGGER.log(
        level,
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')),
    )


def merge_project_workflow_state(
    *,
    project_id: int,
    context: ExtractionRunContext,
    stage: str,
    progress_percent: int,
    status: str | None = None,
    warning_count: int | None = None,
    message: str | None = None,
    counters: Mapping[str, Any] | None = None,
) -> None:
    project = ExamProject.objects.filter(id=project_id).first()
    if project is None:
        return
    state = dict(project.workflow_state) if isinstance(project.workflow_state, dict) else {}
    state.update(
        {
            'stage': str(stage)[:64],
            'progressPercent': min(100, max(0, int(progress_percent))),
            'runId': context.run_id,
            'taskId': context.task_id,
            'attempt': max(1, int(context.attempt)),
            'sourceMapRevision': context.source_map_revision,
            'sourceMapFingerprintPrefix': context.fingerprint_prefix,
            'lastEventAt': timezone.now().isoformat(),
        }
    )
    if warning_count is not None:
        state['warningCount'] = max(0, int(warning_count))
    if message:
        state['message'] = str(message)[:500]
    if counters:
        for key, value in counters.items():
            if not _SAFE_CODE.fullmatch(str(key)[:80]):
                continue
            if isinstance(value, bool):
                state[str(key)[:80]] = value
            elif isinstance(value, (int, float)):
                state[str(key)[:80]] = max(0, value)
            elif value is not None:
                safe = _safe_scalar(value)
                if safe not in (None, 'redacted'):
                    state[str(key)[:80]] = safe

    project.workflow_state = state
    fields = ['workflow_state', 'updated_at']
    if status is not None:
        project.status = status
        fields.insert(0, 'status')
    project.save(update_fields=fields)


_STAGE_CONFIG = {
    'block_detection': (ExamProject.Status.SEGMENTING, 35),
    'question_extraction': (ExamProject.Status.EXTRACTING_QUESTIONS, 50),
    'answer_solution_extraction': (ExamProject.Status.EXTRACTING_ANSWERS, 65),
}


class ObservedExamPrepV4Provider:
    """Log provider-stage timing without exposing provider input or output."""

    def __init__(self, *, delegate: Any, context: ExtractionRunContext) -> None:
        self.delegate = delegate
        self.context = context
        self._last_stage = ''

    @property
    def provider_calls(self) -> int:
        return int(getattr(self.delegate, 'provider_calls', 0))

    def __getattr__(self, name: str):
        return getattr(self.delegate, name)

    def _enter_stage(self, stage: str) -> None:
        if stage == self._last_stage:
            return
        self._last_stage = stage
        status, progress = _STAGE_CONFIG[stage]
        merge_project_workflow_state(
            project_id=self.context.project_id,
            context=self.context,
            stage=stage,
            progress_percent=progress,
            status=status,
        )

    def _invoke(
        self,
        *,
        stage: str,
        operation: str,
        callback: Callable[..., Any],
        safe_fields: Mapping[str, Any],
        kwargs: Mapping[str, Any],
    ) -> Any:
        self._enter_stage(stage)
        started = time.monotonic()
        calls_before = self.provider_calls
        emit_v4_event(
            'exam_prep_v4.extraction.stage_started',
            context=self.context,
            stage=stage,
            operation=operation,
            providerCalls=calls_before,
            **dict(safe_fields),
        )
        try:
            result = callback(**dict(kwargs))
        except Exception as exc:
            emit_v4_event(
                'exam_prep_v4.extraction.stage_failed',
                context=self.context,
                level=logging.ERROR,
                stage=stage,
                operation=operation,
                elapsedMs=round((time.monotonic() - started) * 1000, 2),
                providerCalls=self.provider_calls,
                errorCode=type(exc).__name__,
                **dict(safe_fields),
            )
            raise

        record_count = 0
        if isinstance(result, Mapping):
            for key in ('blocks', 'questions', 'answers'):
                value = result.get(key)
                if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
                    record_count = len(value)
                    break
        emit_v4_event(
            'exam_prep_v4.extraction.stage_completed',
            context=self.context,
            stage=stage,
            operation=operation,
            elapsedMs=round((time.monotonic() - started) * 1000, 2),
            providerCalls=self.provider_calls,
            providerCallsDelta=max(0, self.provider_calls - calls_before),
            proposedRecordCount=record_count,
            **dict(safe_fields),
        )
        return result

    def detect_segment_blocks(self, **kwargs):
        segment = kwargs.get('segment')
        pages = kwargs.get('pages') or ()
        return self._invoke(
            stage='block_detection',
            operation='detect_segment_blocks',
            callback=self.delegate.detect_segment_blocks,
            safe_fields={
                'segmentOrder': getattr(segment, 'order', None),
                'segmentRole': getattr(segment, 'role', None),
                'pageCount': len(pages),
            },
            kwargs=kwargs,
        )

    def extract_questions_batch(self, **kwargs):
        items = kwargs.get('items') or ()
        return self._invoke(
            stage='question_extraction',
            operation='extract_questions_batch',
            callback=self.delegate.extract_questions_batch,
            safe_fields={
                'batchIndex': kwargs.get('batch_index'),
                'batchSize': len(items),
            },
            kwargs=kwargs,
        )

    def extract_answer_solutions_batch(self, **kwargs):
        items = kwargs.get('items') or ()
        return self._invoke(
            stage='answer_solution_extraction',
            operation='extract_answer_solutions_batch',
            callback=self.delegate.extract_answer_solutions_batch,
            safe_fields={
                'batchIndex': kwargs.get('batch_index'),
                'batchSize': len(items),
            },
            kwargs=kwargs,
        )

    def extract_question(self, **kwargs):
        block = kwargs.get('block')
        return self._invoke(
            stage='question_extraction',
            operation='extract_question',
            callback=self.delegate.extract_question,
            safe_fields={'blockId': getattr(block, 'id', None)},
            kwargs=kwargs,
        )

    def extract_answer_solution(self, **kwargs):
        block = kwargs.get('block')
        return self._invoke(
            stage='answer_solution_extraction',
            operation='extract_answer_solution',
            callback=self.delegate.extract_answer_solution,
            safe_fields={'blockId': getattr(block, 'id', None)},
            kwargs=kwargs,
        )

    def safe_provider_metrics(self) -> dict[str, Any]:
        metrics: dict[str, Any] = {'providerCalls': self.provider_calls}
        stats = getattr(self.delegate, 'stats', None)
        if stats is not None:
            metrics.update(
                {
                    'ocrCalls': int(getattr(stats, 'ocr_calls', 0)),
                    'ocrRetries': int(getattr(stats, 'retries', 0)),
                    'ocrFallbackCount': int(getattr(stats, 'fallback_count', 0)),
                    'ocrBboxCalls': int(getattr(stats, 'bbox_calls', 0)),
                }
            )
        return metrics
