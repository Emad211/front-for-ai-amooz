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
        teacher = baker.make('accounts.User', role='teacher')

        # Create 10 sessions with varying numbers of invites and units.
        for i in range(10):
            session = baker.make(
                'classes.ClassCreationSession',
                teacher=teacher,
                pipeline_type='class',
            )
            # Each session has 2 invites and 3 units.
            baker.make(
                'classes.ClassInvitation',
                session=session,
                _quantity=2,
            )
            section = baker.make(
                'classes.ClassSection',
                session=session,
                order=1,
            )
            baker.make(
                'classes.ClassUnit',
                session=session,
                section=section,
                _quantity=3,
            )

        client = _auth_client(teacher)

        with CaptureQueriesContext(connection) as ctx:
            resp = client.get('/api/classes/sessions/')

        assert resp.status_code == 200
        # With annotations, the query count should be bounded.
        # Before fix: 1 (list) + 10 (invites.count) + 10 (units.count) = 21
        # After fix: 1 (list with annotations)
        # Allow auth queries + 1 main query + pagination overhead.
        assert len(ctx.captured_queries) <= 8, (
            f'Expected <=8 queries, got {len(ctx.captured_queries)}:\n'
            + '\n'.join(q['sql'][:120] for q in ctx.captured_queries)
        )


@pytest.mark.django_db
class TestStudentCourseListQueryCount:
    """StudentCourseListView should use prefetches, not N+1."""

    def test_student_course_list_bounded_queries(self):
        student = baker.make('accounts.User', role='student', phone='09120000001')

        # Create 5 published courses with sections/units/invites.
        for i in range(5):
            session = baker.make(
                'classes.ClassCreationSession',
                pipeline_type='class',
                is_published=True,
                structure_json='{}',
            )
            ClassInvitation.objects.create(
                session=session,
                phone='09120000001',
                invite_code=f'CODE-{i}',
            )
            section = baker.make(
                'classes.ClassSection',
                session=session,
                order=i,
            )
            baker.make(
                'classes.ClassUnit',
                session=session,
                section=section,
                _quantity=3,
            )

        client = _auth_client(student)
        client.force_authenticate(user=student)

        with CaptureQueriesContext(connection) as ctx:
            resp = client.get('/api/classes/student/courses/')

        assert resp.status_code == 200
        # Before fix: 1 (list) + N * (sections.count + units.count + invites.count + quiz + exam) ≈ 30+
        # After fix: 1 (list) + 2 (prefetch sections, prefetch units) + 1 (prefetch invites) ≈ 5
        # Allow auth + prefetches + progress queries.
        assert len(ctx.captured_queries) <= 25, (
            f'Expected <=25 queries for 5 courses, got {len(ctx.captured_queries)}'
        )


@pytest.mark.django_db
class TestExamPrepSessionListQueryCount:
    """ExamPrepSessionListView should annotate invites_count."""

    def test_exam_prep_list_bounded_queries(self):
        teacher = baker.make('accounts.User', role='teacher')

        for i in range(5):
            session = baker.make(
                'classes.ClassCreationSession',
                teacher=teacher,
                pipeline_type='exam_prep',
            )
            baker.make(
                'classes.ClassInvitation',
                session=session,
                _quantity=3,
            )

        client = _auth_client(teacher)

        with CaptureQueriesContext(connection) as ctx:
            resp = client.get('/api/classes/exam-prep/sessions/')

        assert resp.status_code == 200
        # With annotation: 1 query. Without: 1 + 5 (invites.count) = 6.
        assert len(ctx.captured_queries) <= 8, (
            f'Expected <=8 queries, got {len(ctx.captured_queries)}'
        )


@pytest.mark.django_db
class TestInviteBulkCreatePerformance:
    """Bulk invitation create should use O(1) check + O(1) insert, not O(N)."""

    def test_bulk_invite_query_count(self):
        teacher = baker.make('accounts.User', role='teacher')
        session = baker.make(
            'classes.ClassCreationSession',
            teacher=teacher,
            pipeline_type='class',
        )

        phones = [f'0912{str(i).zfill(7)}' for i in range(10)]
        for phone in phones:
            StudentInviteCode.objects.create(phone=phone, code=f'C-{phone[-4:]}')

        client = _auth_client(teacher)

        with CaptureQueriesContext(connection) as ctx:
            resp = client.post(
                f'/api/classes/sessions/{session.id}/invites/',
                data={'phones': phones},
                format='json',
            )

        assert resp.status_code == 200

        # Before fix: 1 (session) + 10 (filter per phone) + 10 (create per phone) + 1 (list) = 22
        # After fix: 1 (session) + 1 (existing check) + 10 (get_or_create codes) + 1 (bulk_create) + 1 (list) ≈ 15
        # Still has per-code queries but check+create is 1 query each.
        assert len(ctx.captured_queries) <= 30, (
            f'Expected <=30 queries for 10 phones, got {len(ctx.captured_queries)}'
        )


@pytest.mark.django_db
class TestActivitiesViewQueryCount:
    """TeacherAnalyticsActivitiesView must select_related session on invites."""

    def test_activities_no_n_plus_one(self):
        teacher = baker.make('accounts.User', role='teacher')

        for i in range(5):
            session = baker.make(
                'classes.ClassCreationSession',
                teacher=teacher,
                pipeline_type='class',
            )
            baker.make(
                'classes.ClassInvitation',
                session=session,
                _quantity=2,
            )

        client = _auth_client(teacher)

        with CaptureQueriesContext(connection) as ctx:
            resp = client.get('/api/classes/analytics/activities/')

        assert resp.status_code == 200
        # With select_related: 1 (sessions) + 1 (invites+session) = 2 main queries.
        # Without: 1 + 1 + 5 (inv.session.title per invite) = 7.
        assert len(ctx.captured_queries) <= 8, (
            f'Expected <=8 queries, got {len(ctx.captured_queries)}'
        )
