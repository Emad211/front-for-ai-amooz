"""Query count / N+1 performance tests.

Ensures list endpoints do not exhibit O(N) query patterns when returning
multiple objects — critical for 100 concurrent users.
"""
from __future__ import annotations

import json

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from model_bakery import baker

from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.classes.models import (
    ClassAnnouncement,
    ClassCreationSession,
    ClassInvitation,
    ClassSection,
    ClassUnit,
    StudentInviteCode,
)


def _auth_client(user) -> APIClient:
    refresh = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return client


@pytest.mark.django_db
class TestTeacherSessionListQueryCount:
    """ClassCreationSessionListView should use constant query count."""

    def test_list_sessions_constant_queries(self):
        teacher = baker.make(User, role=User.Role.TEACHER)

        for i in range(10):
            session = baker.make(
                ClassCreationSession,
                teacher=teacher,
                pipeline_type='class',
            )
            baker.make(ClassInvitation, session=session, _quantity=2)
            section = baker.make(ClassSection, session=session, order=1)
            baker.make(ClassUnit, session=session, section=section, _quantity=3)

        client = _auth_client(teacher)

        with CaptureQueriesContext(connection) as ctx:
            resp = client.get('/api/classes/creation-sessions/')

        assert resp.status_code == 200
        assert len(ctx.captured_queries) <= 8, (
            f'Expected <=8 queries, got {len(ctx.captured_queries)}:\n'
            + '\n'.join(q['sql'][:120] for q in ctx.captured_queries)
        )


@pytest.mark.django_db
class TestStudentCourseListQueryCount:
    """StudentCourseListView must be CONSTANT-query, not N+1.

    Progress used to be computed per session (~3 queries each); with the bulk
    helper it is 3 grouped queries total regardless of course count. The bound
    here is tight enough that the old per-session pattern (12 courses → ~36
    progress queries alone) would fail it.
    """

    def _seed(self, student, n):
        for i in range(n):
            session = baker.make(
                ClassCreationSession,
                pipeline_type='class',
                is_published=True,
                structure_json='{}',
            )
            ClassInvitation.objects.create(
                session=session,
                phone=student.phone,
                invite_code=f'CODE-{i}',
            )
            section = baker.make(ClassSection, session=session, order=i)
            baker.make(ClassUnit, session=session, section=section, _quantity=3)

    def test_student_course_list_constant_queries(self):
        student = baker.make(User, role=User.Role.STUDENT, phone='09120000001')
        self._seed(student, 12)

        client = _auth_client(student)

        with CaptureQueriesContext(connection) as ctx:
            resp = client.get('/api/classes/student/courses/')

        assert resp.status_code == 200
        # ~base (auth + sessions + 2 prefetch + invites prefetch) + 3 progress.
        assert len(ctx.captured_queries) <= 14, (
            f'Expected <=14 queries for 12 courses (constant), got '
            f'{len(ctx.captured_queries)}:\n'
            + '\n'.join(q['sql'][:120] for q in ctx.captured_queries)
        )

    def test_progress_does_not_scale_with_course_count(self):
        """Query count for 4 courses must equal that for 16 (truly constant)."""
        s4 = baker.make(User, role=User.Role.STUDENT, phone='09120000004')
        self._seed(s4, 4)
        with CaptureQueriesContext(connection) as ctx4:
            assert _auth_client(s4).get('/api/classes/student/courses/').status_code == 200

        s16 = baker.make(User, role=User.Role.STUDENT, phone='09120000016')
        self._seed(s16, 16)
        with CaptureQueriesContext(connection) as ctx16:
            assert _auth_client(s16).get('/api/classes/student/courses/').status_code == 200

        assert len(ctx16.captured_queries) == len(ctx4.captured_queries), (
            f'Query count scaled with course count: 4→{len(ctx4.captured_queries)}, '
            f'16→{len(ctx16.captured_queries)} (N+1 regression)'
        )


@pytest.mark.django_db
class TestExamPrepSessionListQueryCount:
    """ExamPrepSessionListView should annotate invites_count AND defer the heavy
    transcript/structure/recap columns (lightweight list — see
    ExamPrepSessionListSerializer)."""

    def test_exam_prep_list_bounded_queries(self):
        teacher = baker.make(User, role=User.Role.TEACHER)

        for i in range(5):
            session = baker.make(
                ClassCreationSession,
                teacher=teacher,
                pipeline_type='exam_prep',
                transcript_markdown='X' * 2000,
            )
            baker.make(ClassInvitation, session=session, _quantity=3)

        client = _auth_client(teacher)

        with CaptureQueriesContext(connection) as ctx:
            resp = client.get('/api/classes/exam-prep-sessions/')

        assert resp.status_code == 200
        assert len(ctx.captured_queries) <= 8, (
            f'Expected <=8 queries, got {len(ctx.captured_queries)}'
        )
        # The heavy transcript column must be DEFERRED — never SELECTed for the
        # list. If someone reverts to the detail serializer/queryset, the column
        # reappears in the SQL and this fails.
        sql_blob = ' '.join(q['sql'] for q in ctx.captured_queries)
        assert 'transcript_markdown' not in sql_blob, (
            'transcript_markdown was SELECTed for the exam-prep list — '
            'the .defer() of heavy columns regressed.'
        )


@pytest.mark.django_db
class TestExamPrepListPayloadIsLightweight:
    """The exam-prep list must ship a `question_count` integer, NOT the full
    transcript_markdown / exam_prep_json / parsed exam_prep_data. This is the
    contract guard for the ExamPrepSessionListSerializer slimming."""

    @staticmethod
    def _exam_json(n_questions: int) -> str:
        return json.dumps({
            'exam_prep': {
                'title': 'آزمون نهایی',
                'questions': [{'question_id': f'q{i}'} for i in range(n_questions)],
            }
        })

    def test_heavy_fields_dropped_and_question_count_correct(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        session = baker.make(
            ClassCreationSession,
            teacher=teacher,
            pipeline_type='exam_prep',
            transcript_markdown='X' * 5000,           # heavy — must NOT ship
            exam_prep_json=self._exam_json(7),         # heavy — must NOT ship
        )
        baker.make(ClassInvitation, session=session, _quantity=3)

        resp = _auth_client(teacher).get('/api/classes/exam-prep-sessions/')
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        item = body[0]

        # Heavy payloads gone.
        assert 'transcript_markdown' not in item
        assert 'exam_prep_json' not in item
        assert 'exam_prep_data' not in item

        # Lightweight count surfaced instead, and correct.
        assert item['question_count'] == 7
        assert item['invites_count'] == 3
        # Light metadata the card still needs.
        assert item['title'] == session.title
        assert item['status'] == session.status
        assert 'created_at' in item

    def test_question_count_zero_for_empty_exam_json(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        baker.make(
            ClassCreationSession,
            teacher=teacher,
            pipeline_type='exam_prep',
            exam_prep_json='',
        )
        resp = _auth_client(teacher).get('/api/classes/exam-prep-sessions/')
        assert resp.status_code == 200
        assert resp.json()[0]['question_count'] == 0

    def test_question_count_survives_malformed_exam_json(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        baker.make(
            ClassCreationSession,
            teacher=teacher,
            pipeline_type='exam_prep',
            exam_prep_json='{ this is not valid json',
        )
        resp = _auth_client(teacher).get('/api/classes/exam-prep-sessions/')
        assert resp.status_code == 200
        assert resp.json()[0]['question_count'] == 0


@pytest.mark.django_db
class TestInviteBulkCreatePerformance:
    """Bulk invitation create should use O(1) check + O(1) insert, not O(N)."""

    def test_bulk_invite_query_count(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        session = baker.make(
            ClassCreationSession,
            teacher=teacher,
            pipeline_type='class',
        )

        phones = [f'0912{str(i).zfill(7)}' for i in range(10)]
        for phone in phones:
            StudentInviteCode.objects.get_or_create(
                phone=phone, defaults={'code': f'C-{phone[-4:]}'},
            )

        client = _auth_client(teacher)

        with CaptureQueriesContext(connection) as ctx:
            resp = client.post(
                f'/api/classes/creation-sessions/{session.id}/invites/',
                data={'phones': phones},
                format='json',
            )

        assert resp.status_code == 200
        assert len(ctx.captured_queries) <= 30, (
            f'Expected <=30 queries for 10 phones, got {len(ctx.captured_queries)}'
        )


@pytest.mark.django_db
class TestActivitiesViewQueryCount:
    """TeacherAnalyticsActivitiesView must select_related session on invites."""

    def test_activities_no_n_plus_one(self):
        teacher = baker.make(User, role=User.Role.TEACHER)

        for i in range(5):
            session = baker.make(
                ClassCreationSession,
                teacher=teacher,
                pipeline_type='class',
            )
            baker.make(ClassInvitation, session=session, _quantity=2)

        client = _auth_client(teacher)

        with CaptureQueriesContext(connection) as ctx:
            resp = client.get('/api/classes/teacher/analytics/activities/')

        assert resp.status_code == 200
        assert len(ctx.captured_queries) <= 8, (
            f'Expected <=8 queries, got {len(ctx.captured_queries)}'
        )


@pytest.mark.django_db
class TestStudentNotificationFeedQueryCount:
    """StudentNotificationListView must BOUND the announcements source (not load
    every invited session's announcements then cap), and avoid a per-announcement
    N+1 on `announcement.session` (select_related)."""

    def test_feed_bounded_and_no_per_announcement_n_plus_one(self):
        student = baker.make(User, role=User.Role.STUDENT, phone='09120000050')

        # 12 sessions x 6 announcements = 72 announcements for this student.
        for i in range(12):
            session = baker.make(
                ClassCreationSession,
                pipeline_type='class',
                is_published=True,
            )
            ClassInvitation.objects.create(
                session=session, phone=student.phone, invite_code=f'NC-{i}',
            )
            baker.make(ClassAnnouncement, session=session, _quantity=6)

        client = _auth_client(student)

        with CaptureQueriesContext(connection) as ctx:
            resp = client.get('/api/classes/student/notifications/')

        assert resp.status_code == 200
        # 72 announcements created, no admin/teacher notifs -> feed is exactly the
        # _FEED_LIMIT cap of 50 (also proves the bounded query actually returns the
        # announcements rather than silently empty).
        assert len(resp.json()) == 50
        # Constant query count: auth + read receipts + admin + teacher + ONE
        # bounded announcements query. Without select_related('session') the loop
        # would issue ~50 per-announcement queries (N+1) and blow past this.
        assert len(ctx.captured_queries) <= 9, (
            f'Expected <=9 queries (no per-announcement N+1), got '
            f'{len(ctx.captured_queries)}:\n'
            + '\n'.join(q['sql'][:110] for q in ctx.captured_queries)
        )
