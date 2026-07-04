"""Full-pipeline orchestration: happy-path step chaining + mid-chain cancel.

`test_pipeline_cancel.py` covers cancel-before-start abort + the `_pipeline_cancelled`
helper; `test_pipeline_robustness.py` covers deleted-session aborts, concurrency
caps, cleanup, and step-transition guards. Not duplicated.

Untested: (1) the SUCCESSFUL chain — `process_class_full_pipeline` runs step1→…→
step5 in order and lands on the terminal RECAPPED status; (2) a cooperative
cancel that arrives MID-chain (after a step) stops at the very next checkpoint and
skips the remaining steps. Both drive the real orchestrator with every step
mocked via `_run_pipeline_step` (0 tokens, no LLM/media), which also advances the
session status so the status-gated chain flows.
"""
from __future__ import annotations

import pytest
from model_bakery import baker

from apps.classes import tasks
from apps.classes.models import ClassCreationSession

pytestmark = [pytest.mark.django_db, pytest.mark.integration]

Status = ClassCreationSession.Status

# The status each mocked step leaves behind so the next gate opens.
_STATUS_AFTER = {
    'step1_transcription': Status.TRANSCRIBED,
    'step2_structure': Status.STRUCTURED,
    'step3_prerequisites': Status.PREREQ_EXTRACTED,
    'step4_prereq_teaching': Status.PREREQ_TAUGHT,
    'step5_recap': Status.RECAPPED,
}


def _install_fake_steps(monkeypatch, calls, *, cancel_after: str | None = None):
    def fake_run(task_fn, label, session_id, session):
        calls.append(label)
        updates = {'status': _STATUS_AFTER[label]}
        if cancel_after == label:
            updates['cancel_requested'] = True
        ClassCreationSession.objects.filter(id=session_id).update(**updates)
        return True

    monkeypatch.setattr(tasks, '_run_pipeline_step', fake_run)


def _run(session_id):
    return tasks.process_class_full_pipeline.apply(args=[session_id]).result


def test_full_pipeline_runs_all_five_steps_in_order_to_recapped(monkeypatch):
    session = baker.make(
        ClassCreationSession, pipeline_type='class', status=Status.TRANSCRIBING,
    )
    calls: list[str] = []
    _install_fake_steps(monkeypatch, calls)

    result = _run(session.id)

    assert result['status'] == 'success'
    assert calls == [
        'step1_transcription', 'step2_structure', 'step3_prerequisites',
        'step4_prereq_teaching', 'step5_recap',
    ]
    session.refresh_from_db()
    assert session.status == Status.RECAPPED


def test_cancel_mid_chain_stops_at_next_checkpoint_and_skips_rest(monkeypatch):
    session = baker.make(
        ClassCreationSession, pipeline_type='class', status=Status.TRANSCRIBING,
    )
    calls: list[str] = []
    # The cancel flag is set as step2 completes → the checkpoint right after
    # step2 must halt the pipeline before step3.
    _install_fake_steps(monkeypatch, calls, cancel_after='step2_structure')

    result = _run(session.id)

    assert result['status'] == 'cancelled'
    assert result['stopped_at'] == 'step2'
    assert calls == ['step1_transcription', 'step2_structure']  # 3/4/5 skipped
    session.refresh_from_db()
    assert session.cancel_requested is True


def test_cancel_before_start_runs_no_steps(monkeypatch):
    session = baker.make(
        ClassCreationSession, pipeline_type='class',
        status=Status.TRANSCRIBING, cancel_requested=True,
    )
    calls: list[str] = []
    _install_fake_steps(monkeypatch, calls)

    result = _run(session.id)

    assert result['status'] == 'cancelled'
    assert result['stopped_at'] == 'start'
    assert calls == []  # nothing dispatched


def test_missing_session_is_skipped_safely(monkeypatch):
    calls: list[str] = []
    _install_fake_steps(monkeypatch, calls)
    result = _run(999999)
    assert result['status'] == 'skipped'
    assert calls == []
