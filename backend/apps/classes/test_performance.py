"""Query count / N+1 performance tests.

Ensures list endpoints do not exhibit O(N) query patterns when returning
multiple objects — critical for 100 concurrent users.
"""
from __future__ import annotations

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from model_bakery import baker

from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.classes.models import (
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
    """StudentCourseListView should use prefetches, not N+1."""

    def test_student_course_list_bounded_queries(self):
        student = baker.make(User, role=User.Role.STUDENT, phone='09120000001')

        for i in range(5):
            session = baker.make(
                ClassCreationSession,
                pipeline_type='class',
                is_published=True,
                structure_json='{}',
            )
            ClassInvitation.objects.create(
                session=session,
                phone='09120000001',
                invite_code=f'CODE-{i}',
            )
            section = baker.make(ClassSection, session=session, order=i)
            baker.make(ClassUnit, session=session, section=section, _quantity=3)

        client = _auth_client(student)

        with CaptureQueriesContext(connection) as ctx:
            resp = client.get('/api/classes/student/courses/')

        assert resp.status_code == 200
        assert len(ctx.captured_queries) <= 25, (
            f'Expected <=25 queries for 5 courses, got {len(ctx.captured_queries)}'
        )


@pytest.mark.django_db
class TestExamPrepSessionListQueryCount:
    """ExamPrepSessionListView should annotate invites_count."""

    def test_exam_prep_list_bounded_queries(self):
        teacher = baker.make(User, role=User.Role.TEACHER)

        for i in range(5):
            session = baker.make(
                ClassCreationSession,
                teacher=teacher,
                pipeline_type='exam_prep',
            )
            baker.make(ClassInvitation, session=session, _quantity=3)

        client = _auth_client(teacher)

        with CaptureQueriesContext(connection) as ctx:
            resp = client.get('/api/classes/exam-prep-sessions/')

        assert resp.status_code == 200
        assert len(ctx.captured_queries) <= 8, (
            f'Expected <=8 queries, got {len(ctx.captured_queries)}'
        )


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
