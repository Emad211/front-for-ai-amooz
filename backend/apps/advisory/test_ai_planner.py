"""Risman steps 5+6 (wave R3) — the AI plan-draft door, contract-first.

Zero real provider tokens (roadmap ق۴): the structured-LLM seam is patched at
the module boundary, so the tests pin OUR half of the contract —

* **prompt contract** — the ``ai_plan_draft`` key exists with its four
  placeholders and the JSON field names, byte-for-byte;
* **evidence (wave 6a)** — the prompt carries the student's capped evidence
  block (goal, open mistakes, due reviews, backlog, recent exams) rendered
  from real data; an empty engagement still renders empty structures, never
  a leftover placeholder, and the JSON stays under a hard char budget;
* **pipeline** — a valid model answer lands as a DRAFT through ``save_draft``
  (single slot upserted, always DRAFT — never auto-published);
* **semantics** — a subject outside the student's selection, cap violations,
  empty answers and empty prompts are 400s with pinned Persian wording, while
  provider chaos (StructuredOutputError, connection errors) is the pinned 502;
* **voice (step 6)** — missing/oversized audio → 400; a transcript rides the
  same text path; transcription failure is 502 too;
* **wire** — the access matrix (student 403, anon 401, stranger advisor 404)
  and the success shape (201 + detail + plan).
"""

from __future__ import annotations

import datetime
import json
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from model_bakery import baker
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.advisory.models import (
    AdvisoryEngagement,
    AdvisoryGoal,
    DailyLog,
    DailyLogItem,
    MistakeEntry,
    StudentSubject,
    StudyExamScore,
    StudyPlan,
    StudyPlanItem,
    Subject,
    TopicProgress,
)
from apps.advisory.services import ai_planner
from apps.commons.llm_prompts import PROMPTS
from apps.commons.structured_llm import StructuredOutputError

User = get_user_model()
Status = AdvisoryEngagement.Status
PlanStatus = StudyPlan.Status
Mode = AdvisoryEngagement.Mode

pytestmark = [pytest.mark.django_db, pytest.mark.api]

GRADE = '10'

URL = '/api/advisory/students/{pk}/plans/ai-draft/'

MSG_EMPTY_PROMPT = 'متن درخواست را بنویسید.'
MSG_LONG_PROMPT = 'متن درخواست حداکثر ۲۰۰۰ نویسه است.'
MSG_NO_SUBJECTS = 'ابتدا درس‌های دانش‌آموز را انتخاب کنید.'
MSG_FOREIGN_SUBJECT = 'هوش مصنوعی فقط مجاز به انتخاب درس‌های شماست.'
MSG_NO_ITEMS = 'هوش مصنوعی هیچ ردیفی پیشنهاد نداد؛ دوباره تلاش کنید.'
MSG_MINUTES = 'دقیقه‌ی هر ردیف باید بین ۱۵ تا ۴۸۰ باشد.'
MSG_DAY = 'روز پیشنهادی باید بین ۰ تا ۶ باشد.'
MSG_TOTAL = 'مجموع دقیقه‌های پیشنهادی از سقف هفتگی (۳۶۰۰) گذشت.'
MSG_OVERLAP = 'این بازه با برنامهٔ منتشرشدهٔ دیگری همپوشانی دارد.'
MSG_UNAVAILABLE = 'سرویس هوش مصنوعی در دسترس نیست.'
MSG_NO_AUDIO = 'فایل صوتی ارسال نشد.'
MSG_AUDIO_TOO_LARGE = 'حجم فایل صوتی حداکثر ۵ مگابایت است.'
MSG_SILENT_AUDIO = 'صدای ارسالی قابل تشخیص نبود؛ دوباره تلاش کنید.'


# ── fixture helpers (mirroring test_study_plans.py) ───────────────────────────

def _today() -> datetime.date:
    return timezone.localdate()


def _shift(days: int) -> datetime.date:
    return _today() + datetime.timedelta(days=days)


def _auth(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _advisor(username='adv', **kwargs):
    return baker.make(User, username=username, role=User.Role.ADVISOR, **kwargs)


def _student(username='stu', phone='09120000001', *, grade=GRADE, major=None, **kwargs):
    user = baker.make(User, username=username, role=User.Role.STUDENT, phone=phone, **kwargs)
    profile = user.studentprofile
    profile.grade = grade
    profile.major = major
    profile.save(update_fields=['grade', 'major'])
    return user


def _engagement(advisor, student, *, status=Status.ACTIVE, **kwargs):
    defaults = {
        'invited_phone': student.phone or '',
        'mode': Mode.FREELANCE,
        'organization': None,
        'status': status,
        'started_on': _shift(-30),
    }
    defaults.update(kwargs)
    return AdvisoryEngagement.objects.create(advisor=advisor, student=student, **defaults)


def _subject(name, *, grade=GRADE, major=None, is_active=True):
    return baker.make(
        Subject, name=name, grade=grade, major=major, is_active=is_active,
    )


def _selection(engagement, *subjects):
    return [
        baker.make(StudentSubject, engagement=engagement, subject=s, is_active=True)
        for s in subjects
    ]


def _url(engagement) -> str:
    return URL.format(pk=engagement.pk)


def _answer(items) -> ai_planner._AIPlanDraft:
    """A validated payload exactly as ``generate_structured`` would return."""
    return ai_planner._AIPlanDraft(
        items=[ai_planner._AIPlanItem(**item) for item in items],
    )


# ── prompt contract (byte-for-byte, guarded per §prompts) ────────────────────

class TestPromptContract:
    def test_key_exists_with_placeholders_and_field_names(self):
        prompt = PROMPTS['ai_plan_draft']
        assert '{week_start_iso}' in prompt
        assert '{free_prompt}' in prompt
        assert '{subjects_json}' in prompt
        assert '{evidence_json}' in prompt
        # The JSON vocabulary the resolver depends on — a renamed key here
        # would silently break _AIPlanItem parsing on every real call.
        for field in ('dayOffset', 'subjectId', 'plannedMinutes', 'topic'):
            assert field in prompt
        # The hard caps must be stated to the model, not just enforced here.
        assert '15..480' in prompt
        assert '0..6' in prompt

    def test_render_fills_every_placeholder(self):
        subjects = [{'id': 3, 'name': 'ریاضی'}]
        week = datetime.date(2026, 8, 29)
        rendered = ai_planner._render_prompt(
            'دو ساعت ریاضی', subjects, week, '{"goalTitle": "قبولی کنکور"}',
        )
        assert '{week_start_iso}' not in rendered
        assert '{free_prompt}' not in rendered
        assert '{subjects_json}' not in rendered
        assert '{evidence_json}' not in rendered
        assert week.isoformat() in rendered
        assert 'دو ساعت ریاضی' in rendered
        assert 'ریاضی' in rendered
        assert 'قبولی کنکور' in rendered


# ── evidence block (wave 6a): the DB half the model never saw ────────────────

GOAL_TITLE = 'پزشکی، دانشگاه شهید بهشتی'


def _seed_evidence(engagement, selection):
    """Goal + 2 open mistakes + 1 due review + 1 backlog row + 2 exam scores.

    One resolved mistake rides along to prove the filter: a closed loop
    never reaches the model.
    """
    today = _today()
    AdvisoryGoal.objects.create(engagement=engagement, target_title=GOAL_TITLE)
    MistakeEntry.objects.create(
        engagement=engagement, student_subject=selection, topic='اصطکاک',
        error_type=MistakeEntry.ErrorType.CONCEPT,
        priority=MistakeEntry.Priority.HIGH,
    )
    MistakeEntry.objects.create(
        engagement=engagement, student_subject=selection, topic='حد',
        error_type=MistakeEntry.ErrorType.FORGET,
        priority=MistakeEntry.Priority.MEDIUM,
    )
    MistakeEntry.objects.create(
        engagement=engagement, student_subject=selection, topic='خطای حل‌شده',
        error_type=MistakeEntry.ErrorType.TIME,
        priority=MistakeEntry.Priority.HIGH, is_resolved=True,
    )
    TopicProgress.objects.create(
        engagement=engagement, student_subject=selection, topic='توابع',
        status=TopicProgress.Status.NEEDS_REVIEW,
        next_review_at=today - datetime.timedelta(days=1),
    )
    # Yesterday's published 60-minute row with only 20 minutes logged →
    # exactly one uncompensated backlog row (mirrors test_growth's seeding).
    log = DailyLog.objects.create(
        engagement=engagement, log_date=today - datetime.timedelta(days=1),
    )
    DailyLogItem.objects.create(
        log=log, student_subject=selection, actual_minutes=20,
    )
    plan = StudyPlan.objects.create(
        engagement=engagement, start_date=today - datetime.timedelta(days=1),
        duration_days=3, status=StudyPlan.Status.PUBLISHED,
    )
    StudyPlanItem.objects.create(
        plan=plan, day_offset=0, student_subject=selection,
        planned_minutes=60, topic='لگاریتم',
    )
    StudyExamScore.objects.create(
        engagement=engagement, title='آزمون خرداد', exam_kind='SCHOOL',
        exam_date=today - datetime.timedelta(days=10),
        score_percent=Decimal('62.00'), tara=5400,
    )
    StudyExamScore.objects.create(
        engagement=engagement, title='آزمون مرداد', exam_kind='SCHOOL',
        exam_date=today - datetime.timedelta(days=3),
        score_percent=Decimal('78.50'),
    )


class TestStudentEvidence:
    def test_shapes_from_seeded_data(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        _seed_evidence(engagement, _selection(engagement, math)[0])

        evidence = ai_planner._student_evidence(engagement)

        assert evidence['goal_title'] == GOAL_TITLE
        assert evidence['open_mistakes'] == [
            {'topic': 'اصطکاک', 'error_type': 'CONCEPT', 'priority': 'HIGH'},
            {'topic': 'حد', 'error_type': 'FORGET', 'priority': 'MEDIUM'},
        ]
        assert evidence['due_reviews'] == [
            {'subject': 'ریاضی', 'topic': 'توابع'},
        ]
        assert evidence['backlog'] == [
            {'subject': 'ریاضی', 'topic': 'لگاریتم', 'planned': 60, 'actual': 20},
        ]
        assert evidence['recent_exams'] == [
            {'date': _shift(-3).isoformat(), 'percent': 78.5, 'tara': None},
            {'date': _shift(-10).isoformat(), 'percent': 62.0, 'tara': 5400},
        ]

    def test_caps_keep_the_priority_signals(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        selection = _selection(engagement, math)[0]
        # Two older MEDIUM rows, then five newer HIGH rows → the HIGH block
        # leads the list and the cap keeps exactly five open mistakes.
        for topic in ('قدیمی ۱', 'قدیمی ۲'):
            MistakeEntry.objects.create(
                engagement=engagement, student_subject=selection, topic=topic,
                error_type=MistakeEntry.ErrorType.TIME,
                priority=MistakeEntry.Priority.MEDIUM,
            )
        for index in range(5):
            MistakeEntry.objects.create(
                engagement=engagement, student_subject=selection,
                topic=f'فوری {index + 1}',
                error_type=MistakeEntry.ErrorType.CONCEPT,
                priority=MistakeEntry.Priority.HIGH,
            )
        # Seven due reviews with distinct dates → the five most overdue stay.
        for index in range(7):
            TopicProgress.objects.create(
                engagement=engagement, student_subject=selection,
                topic=f'مبحث {index + 1}',
                status=TopicProgress.Status.NEEDS_REVIEW,
                next_review_at=_shift(-(index + 1)),
            )

        evidence = ai_planner._student_evidence(engagement)

        assert [m['priority'] for m in evidence['open_mistakes']] == ['HIGH'] * 5
        assert {m['topic'] for m in evidence['open_mistakes']} == {
            f'فوری {index + 1}' for index in range(5)
        }
        assert [r['topic'] for r in evidence['due_reviews']] == [
            f'مبحث {index}' for index in range(7, 2, -1)
        ]

    def test_evidence_reaches_the_model_prompt(self, monkeypatch):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        _seed_evidence(engagement, _selection(engagement, math)[0])
        seen = {}

        def fake_generate(*, schema, messages, **kwargs):
            seen['content'] = messages[0]['content']
            return _answer(
                [{'dayOffset': 0, 'subjectId': math.id, 'plannedMinutes': 60}],
            )

        monkeypatch.setattr(ai_planner, 'generate_structured', fake_generate)
        ai_planner.draft_plan_from_text(engagement, 'برنامهٔ این هفته', advisor)

        # The evidence actually reaches the text the model sees.
        assert 'goalTitle' in seen['content']
        assert GOAL_TITLE in seen['content']
        assert 'اصطکاک' in seen['content']
        assert 'توابع' in seen['content']
        assert 'لگاریتم' in seen['content']

    def test_empty_engagement_renders_empty_structures(self, monkeypatch):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        _selection(engagement, math)
        seen = {}

        def fake_generate(*, schema, messages, **kwargs):
            seen['content'] = messages[0]['content']
            return _answer(
                [{'dayOffset': 0, 'subjectId': math.id, 'plannedMinutes': 60}],
            )

        monkeypatch.setattr(ai_planner, 'generate_structured', fake_generate)
        ai_planner.draft_plan_from_text(engagement, 'برنامه بساز', advisor)

        content = seen['content']
        assert '{evidence_json}' not in content
        assert 'None' not in content
        # No data still renders every key — empty structures, never blanks.
        assert '"goalTitle": null' in content
        assert '"openMistakes": []' in content

    def test_ten_backlog_rows_keep_the_prompt_bounded(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        selection = _selection(engagement, math)[0]
        today = _today()
        # Ten published under-logged days → ten backlog rows in analytics,
        # but only the three most recent reach the evidence block.
        for offset in range(2, 12):
            plan = StudyPlan.objects.create(
                engagement=engagement,
                start_date=today - datetime.timedelta(days=offset),
                duration_days=1, status=StudyPlan.Status.PUBLISHED,
            )
            StudyPlanItem.objects.create(
                plan=plan, day_offset=0, student_subject=selection,
                planned_minutes=60,
            )

        evidence = ai_planner._student_evidence(engagement)
        block = ai_planner._evidence_json(evidence)

        assert len(evidence['backlog']) == 3
        assert len(block) <= ai_planner.MAX_EVIDENCE_JSON_CHARS
        assert len(json.loads(block)['backlog']) == 3

    def test_evidence_json_trims_backlog_then_exams_under_budget(self):
        # A deliberately over-budget block: every list at its cap with
        # 190-char topics. The budget must hold and the least-priority
        # signals (backlog, then exams) must be dropped first.
        fat = {
            'goal_title': 'ه' * 120,
            'open_mistakes': [
                {
                    'topic': 'مبحث' + 'ی' * 190,
                    'error_type': 'CONCEPT',
                    'priority': 'HIGH',
                }
                for _ in range(5)
            ],
            'due_reviews': [
                {'subject': 'ریاضی', 'topic': 'ت' * 190} for _ in range(5)
            ],
            'backlog': [
                {'subject': 'ریاضی', 'topic': 'ل' * 190, 'planned': 60, 'actual': 0}
                for _ in range(3)
            ],
            'recent_exams': [
                {'date': '2026-08-01', 'percent': 50.0, 'tara': 5000}
                for _ in range(3)
            ],
        }

        text = ai_planner._evidence_json(fat)

        assert len(text) <= ai_planner.MAX_EVIDENCE_JSON_CHARS
        payload = json.loads(text)
        assert payload['backlog'] == []
        assert payload['recentExams'] == []
        assert payload['goalTitle'] == 'ه' * 120
        assert payload['openMistakes']


# ── service: the text pipeline ────────────────────────────────────────────────

class TestTextPipeline:
    def test_valid_answer_lands_as_the_draft_slot(self, monkeypatch):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math, physics = _subject('ریاضی'), _subject('فیزیک')
        _selection(engagement, math, physics)
        seen = {}

        def fake_generate(*, schema, messages, **kwargs):
            seen['content'] = messages[0]['content']
            return _answer([
                {'dayOffset': 0, 'subjectId': math.id, 'plannedMinutes': 120,
                 'topic': 'مشاهدات نجومی'},
                {'dayOffset': 2, 'subjectId': physics.id, 'plannedMinutes': 45},
            ])

        monkeypatch.setattr(ai_planner, 'generate_structured', fake_generate)
        plan = ai_planner.draft_plan_from_text(
            engagement, 'دو ساعت ریاضی روز اول', advisor,
        )

        assert StudyPlan.objects.count() == 1
        assert plan.status == PlanStatus.DRAFT
        assert plan.start_date == ai_planner.calendar.week_start_of(_today())
        stored = {
            (i.day_offset, i.student_subject.subject_id): (i.planned_minutes, i.topic)
            for i in plan.items.all()
        }
        assert stored == {
            (0, math.id): (120, 'مشاهدات نجومی'),
            (2, physics.id): (45, ''),
        }
        # The prompt the model saw carried the menu and the request itself.
        assert f'"id": {math.id}' in seen['content']
        assert 'ریاضی' in seen['content']
        assert 'فیزیک' in seen['content']
        assert 'دو ساعت ریاضی روز اول' in seen['content']

    def test_second_call_upserts_the_same_slot(self, monkeypatch):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        _selection(engagement, math)
        monkeypatch.setattr(
            ai_planner, 'generate_structured',
            lambda *, schema, messages, **kwargs: _answer(
                [{'dayOffset': 1, 'subjectId': math.id, 'plannedMinutes': 60}],
            ),
        )
        ai_planner.draft_plan_from_text(engagement, 'اول', advisor)
        second = ai_planner.draft_plan_from_text(engagement, 'دوم', advisor)
        assert StudyPlan.objects.count() == 1
        assert second.items.count() == 1

    def test_model_answer_never_auto_publishes(self, monkeypatch):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        _selection(engagement, math)
        monkeypatch.setattr(
            ai_planner, 'generate_structured',
            lambda *, schema, messages, **kwargs: _answer(
                [{'dayOffset': 0, 'subjectId': math.id, 'plannedMinutes': 30}],
            ),
        )
        plan = ai_planner.draft_plan_from_text(engagement, 'هر روز ریاضی', advisor)
        assert plan.status == PlanStatus.DRAFT

    def test_empty_and_oversized_prompts(self, monkeypatch):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        with pytest.raises(ai_planner.AIPlannerError) as ei:
            ai_planner.draft_plan_from_text(engagement, '   ', advisor)
        assert str(ei.value) == MSG_EMPTY_PROMPT
        with pytest.raises(ai_planner.AIPlannerError) as ei:
            ai_planner.draft_plan_from_text(engagement, 'x' * 2001, advisor)
        assert str(ei.value) == MSG_LONG_PROMPT

    def test_no_active_subjects(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        with pytest.raises(ai_planner.AIPlannerError) as ei:
            ai_planner.draft_plan_from_text(engagement, 'برنامه بساز', advisor)
        assert str(ei.value) == MSG_NO_SUBJECTS

    def test_inactive_selection_is_not_a_menu(self, monkeypatch):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        baker.make(
            StudentSubject, engagement=engagement, subject=math, is_active=False,
        )
        with pytest.raises(ai_planner.AIPlannerError) as ei:
            ai_planner.draft_plan_from_text(engagement, 'برنامه بساز', advisor)
        assert str(ei.value) == MSG_NO_SUBJECTS

    def test_unknown_subject_is_rejected(self, monkeypatch):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math, other = _subject('ریاضی'), _subject('شیمی')
        _selection(engagement, math)  # «شیمی» ساخته شد ولی انتخاب نشد
        monkeypatch.setattr(
            ai_planner, 'generate_structured',
            lambda *, schema, messages, **kwargs: _answer(
                [{'dayOffset': 0, 'subjectId': other.id, 'plannedMinutes': 60}],
            ),
        )
        with pytest.raises(ai_planner.AIPlannerError) as ei:
            ai_planner.draft_plan_from_text(engagement, 'برنامه بساز', advisor)
        assert str(ei.value) == MSG_FOREIGN_SUBJECT

    def test_caps_are_enforced_on_the_model(self, monkeypatch):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        _selection(engagement, math)
        cases = [
            ([{'dayOffset': 0, 'subjectId': math.id, 'plannedMinutes': 10}], MSG_MINUTES),
            ([{'dayOffset': 0, 'subjectId': math.id, 'plannedMinutes': 481}], MSG_MINUTES),
            ([{'dayOffset': 7, 'subjectId': math.id, 'plannedMinutes': 60}], MSG_DAY),
            ([], MSG_NO_ITEMS),
        ]
        for answer, message in cases:
            monkeypatch.setattr(
                ai_planner, 'generate_structured',
                lambda *, schema, messages, _a=answer, **kwargs: _answer(_a),
            )
            with pytest.raises(ai_planner.AIPlannerError) as ei:
                ai_planner.draft_plan_from_text(engagement, 'برنامه بساز', advisor)
            assert str(ei.value) == message

    def test_weekly_total_cap(self, monkeypatch):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math, physics = _subject('ریاضی'), _subject('فیزیک')
        _selection(engagement, math, physics)
        # 8 distinct (day, subject) rows × 480 = 3840 > 3600 → the 8th trips.
        items = [
            {'dayOffset': d, 'subjectId': s.id, 'plannedMinutes': 480}
            for d in range(4)
            for s in (math, physics)
        ]
        assert len(items) == 8
        monkeypatch.setattr(
            ai_planner, 'generate_structured',
            lambda *, schema, messages, **kwargs: _answer(items),
        )
        with pytest.raises(ai_planner.AIPlannerError) as ei:
            ai_planner.draft_plan_from_text(engagement, 'فشرده بخوان', advisor)
        assert str(ei.value) == MSG_TOTAL

    def test_duplicate_model_rows_collapse(self, monkeypatch):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        _selection(engagement, math)
        monkeypatch.setattr(
            ai_planner, 'generate_structured',
            lambda *, schema, messages, **kwargs: _answer([
                {'dayOffset': 0, 'subjectId': math.id, 'plannedMinutes': 60},
                {'dayOffset': 0, 'subjectId': math.id, 'plannedMinutes': 90},
            ]),
        )
        plan = ai_planner.draft_plan_from_text(engagement, 'تکراری', advisor)
        assert plan.items.count() == 1
        assert plan.items.first().planned_minutes == 90

    def test_provider_chaos_is_the_pinned_502(self, monkeypatch):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        _selection(engagement, math)

        def boom(*, schema, messages, **kwargs):
            raise StructuredOutputError('unrepairable')

        monkeypatch.setattr(ai_planner, 'generate_structured', boom)
        with pytest.raises(ai_planner.AIUnavailable) as ei:
            ai_planner.draft_plan_from_text(engagement, 'برنامه بساز', advisor)
        assert str(ei.value) == MSG_UNAVAILABLE

        def conn_fail(*, schema, messages, **kwargs):
            raise ConnectionError('gateway down')

        monkeypatch.setattr(ai_planner, 'generate_structured', conn_fail)
        with pytest.raises(ai_planner.AIUnavailable) as ei:
            ai_planner.draft_plan_from_text(engagement, 'برنامه بساز', advisor)
        assert str(ei.value) == MSG_UNAVAILABLE


# ── voice (step 6): transcription rides the same text path ────────────────────

def _patch_transcribe(monkeypatch, transcript=''):
    """Patch the transcription seam at its source module — the planner imports
    it lazily at call time, so the source attribute is the stable seam."""
    calls: dict = {}

    def fake_transcribe(*, data, mime_type):
        calls['data'] = data
        calls['mime_type'] = mime_type
        return transcript, 'fake-provider', 'fake-model'

    monkeypatch.setattr(
        'apps.classes.services.transcription.transcribe_media_bytes',
        fake_transcribe,
    )
    return calls


class TestVoicePipeline:
    def test_transcript_rides_the_text_path(self, monkeypatch):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        _selection(engagement, math)
        calls = _patch_transcribe(
            monkeypatch, transcript='زهرا این هفته روزی دو ساعت ریاضی بخواند',
        )
        monkeypatch.setattr(
            ai_planner, 'generate_structured',
            lambda *, schema, messages, **kwargs: _answer(
                [{'dayOffset': 0, 'subjectId': math.id, 'plannedMinutes': 120}],
            ),
        )

        plan = ai_planner.draft_plan_from_voice(
            engagement, data=b'fake-audio-bytes', mime_type='audio/webm',
            user=advisor,
        )

        assert calls['data'] == b'fake-audio-bytes'
        assert calls['mime_type'] == 'audio/webm'
        assert plan.status == PlanStatus.DRAFT
        assert plan.items.count() == 1

    def test_missing_and_oversized_audio(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)

        with pytest.raises(ai_planner.AudioMissing) as ei:
            ai_planner.draft_plan_from_voice(engagement, data=b'', mime_type='')
        assert str(ei.value) == MSG_NO_AUDIO

        with pytest.raises(ai_planner.AudioTooLarge) as ei:
            ai_planner.draft_plan_from_voice(
                engagement,
                data=b'x' * (ai_planner.MAX_VOICE_BYTES + 1),
                mime_type='',
            )
        assert str(ei.value) == MSG_AUDIO_TOO_LARGE

    def test_silence_is_a_retryable_400(self, monkeypatch):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        _patch_transcribe(monkeypatch, transcript='   ')

        with pytest.raises(ai_planner.AIPlannerError) as ei:
            ai_planner.draft_plan_from_voice(
                engagement, data=b'quiet', mime_type='audio/webm',
            )
        assert str(ei.value) == MSG_SILENT_AUDIO

    def test_transcription_outage_is_the_pinned_502(self, monkeypatch):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)

        def down(*, data, mime_type):
            raise ConnectionError('stt down')

        monkeypatch.setattr(
            'apps.classes.services.transcription.transcribe_media_bytes', down,
        )
        with pytest.raises(ai_planner.AIUnavailable) as ei:
            ai_planner.draft_plan_from_voice(
                engagement, data=b'x', mime_type='audio/webm',
            )
        assert str(ei.value) == MSG_UNAVAILABLE


# ── wire: the endpoint itself ─────────────────────────────────────────────────

class TestAIDraftEndpoint:
    def test_text_happy_path_is_201_with_a_draft(self, monkeypatch):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        _selection(engagement, math)
        monkeypatch.setattr(
            ai_planner, 'generate_structured',
            lambda *, schema, messages, **kwargs: _answer(
                [{'dayOffset': 1, 'subjectId': math.id, 'plannedMinutes': 90}],
            ),
        )

        resp = _auth(advisor).post(
            _url(engagement), {'prompt': 'برنامهٔ این هفته را بساز'}, format='json',
        )

        assert resp.status_code == 201
        body = resp.json()
        assert body['plan']['status'] == PlanStatus.DRAFT
        assert StudyPlan.objects.filter(engagement=engagement).count() == 1

    def test_voice_multipart_happy_path(self, monkeypatch):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        _selection(engagement, math)
        _patch_transcribe(monkeypatch, transcript='روزی دو ساعت ریاضی')
        monkeypatch.setattr(
            ai_planner, 'generate_structured',
            lambda *, schema, messages, **kwargs: _answer(
                [{'dayOffset': 0, 'subjectId': math.id, 'plannedMinutes': 120}],
            ),
        )
        upload = SimpleUploadedFile(
            'note.webm', b'audio-bytes', content_type='audio/webm',
        )

        resp = _auth(advisor).post(
            _url(engagement),
            {'voice': 'true', 'audio': upload},
            format='multipart',
        )

        assert resp.status_code == 201
        assert StudyPlan.objects.filter(engagement=engagement).count() == 1

    def test_voice_without_file_is_the_pinned_400(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)

        resp = _auth(advisor).post(
            _url(engagement), {'voice': 'true'}, format='multipart',
        )

        assert resp.status_code == 400
        assert resp.json()['detail'] == MSG_NO_AUDIO

    def test_empty_prompt_is_the_pinned_400(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)

        resp = _auth(advisor).post(_url(engagement), {'prompt': ''}, format='json')

        assert resp.status_code == 400
        assert resp.json()['detail'] == MSG_EMPTY_PROMPT

    def test_provider_outage_is_the_pinned_502(self, monkeypatch):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        math = _subject('ریاضی')
        _selection(engagement, math)

        def boom(*, schema, messages, **kwargs):
            raise ConnectionError('gateway down')

        monkeypatch.setattr(ai_planner, 'generate_structured', boom)

        resp = _auth(advisor).post(
            _url(engagement), {'prompt': 'برنامه بساز'}, format='json',
        )

        assert resp.status_code == 502
        assert resp.json()['detail'] == MSG_UNAVAILABLE

    def test_student_is_403(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)

        resp = _auth(student).post(
            _url(engagement), {'prompt': 'برنامه بساز'}, format='json',
        )

        assert resp.status_code == 403

    def test_stranger_advisor_is_404(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)
        stranger = _advisor(username='stranger')

        resp = _auth(stranger).post(
            _url(engagement), {'prompt': 'برنامه بساز'}, format='json',
        )

        assert resp.status_code == 404

    def test_anonymous_is_401(self):
        advisor, student = _advisor(), _student()
        engagement = _engagement(advisor, student)

        resp = APIClient().post(
            _url(engagement), {'prompt': 'برنامه بساز'}, format='json',
        )

        assert resp.status_code == 401