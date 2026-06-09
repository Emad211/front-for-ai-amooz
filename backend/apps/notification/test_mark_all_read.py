"""Tests for MarkAllNotificationsReadView (POST /api/notifications/read-all/).

The view must mark EVERY relevant notification read for the caller (admin
broadcasts targeted at them, class announcements for their invited sessions, and
teacher messages addressed to them) — and must do so by fetching only ids
(values_list), never materializing full model rows. A student in many classes
with many announcements must not load every announcement body into memory just
to read .id, and the query count must stay CONSTANT as announcements grow.
"""
from __future__ import annotations

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from model_bakery import baker
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.classes.models import (
    ClassAnnouncement,
    ClassCreationSession,
    ClassInvitation,
)
from apps.notification.models import (
    AdminNotification,
    NotificationReadReceipt,
    TeacherNotification,
    TeacherNotificationRecipient,
)


def _student(phone='09120000001'):
    return User.objects.create_user(
        username=f'stu-{phone}', password='p', role=User.Role.STUDENT, phone=phone,
    )


def _invited_session(student, *, announcements=0):
    teacher = User.objects.create_user(
        username=f't-{student.phone}', password='p',
        role=User.Role.TEACHER, phone=f'0915{student.phone[-7:]}',
    )
    session = baker.make(
        ClassCreationSession, teacher=teacher, pipeline_type='class', is_published=True,
    )
    ClassInvitation.objects.create(
        session=session, phone=student.phone, invite_code=f'I-{student.phone}',
    )
    if announcements:
        baker.make(ClassAnnouncement, session=session, _quantity=announcements)
    return session


@pytest.mark.django_db
class TestMarkAllNotificationsRead:
    def test_marks_admin_announcement_and_teacher_notifications(self):
        student = _student()
        session = _invited_session(student, announcements=3)

        AdminNotification.objects.create(title='all', message='m', audience=AdminNotification.Audience.ALL)
        AdminNotification.objects.create(title='stu', message='m', audience=AdminNotification.Audience.STUDENTS)
        # A teacher-audience admin notif must NOT be marked read for a student.
        AdminNotification.objects.create(title='tch', message='m', audience=AdminNotification.Audience.TEACHERS)

        tn = TeacherNotification.objects.create(teacher=session.teacher, title='hi', message='m')
        TeacherNotificationRecipient.objects.create(notification=tn, phone=student.phone)

        client = APIClient()
        client.force_authenticate(user=student)
        resp = client.post('/api/notifications/read-all/')
        assert resp.status_code == 200

        marked = set(
            NotificationReadReceipt.objects.filter(user=student)
            .values_list('notification_id', flat=True)
        )
        ann_ids = list(ClassAnnouncement.objects.filter(session=session).values_list('id', flat=True))
        admin_ids = list(
            AdminNotification.objects.filter(audience__in=['all', 'students'])
            .values_list('id', flat=True)
        )
        expected = (
            {f'admin-{i}' for i in admin_ids}
            | {f'announcement-{i}' for i in ann_ids}
            | {f'teacher-{tn.id}'}
        )
        assert expected <= marked
        # The teacher-audience admin notif is not part of a student's feed.
        tch_id = AdminNotification.objects.get(audience='teachers').id
        assert f'admin-{tch_id}' not in marked

    def test_query_count_constant_as_announcements_grow(self):
        s_small = _student('09120000010')
        _invited_session(s_small, announcements=3)
        client = APIClient()
        client.force_authenticate(user=s_small)
        with CaptureQueriesContext(connection) as ctx_small:
            assert client.post('/api/notifications/read-all/').status_code == 200

        s_big = _student('09120000020')
        _invited_session(s_big, announcements=25)
        client2 = APIClient()
        client2.force_authenticate(user=s_big)
        with CaptureQueriesContext(connection) as ctx_big:
            assert client2.post('/api/notifications/read-all/').status_code == 200

        # values_list keeps each SELECT a single bounded query and bulk_create is
        # one INSERT — so 3 vs 25 announcements must issue the SAME number of queries.
        assert len(ctx_big.captured_queries) == len(ctx_small.captured_queries), (
            f'Query count scaled with announcement count: '
            f'3->{len(ctx_small.captured_queries)}, 25->{len(ctx_big.captured_queries)}'
        )
