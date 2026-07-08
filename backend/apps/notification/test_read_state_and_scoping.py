"""Notification read-state: per-user isolation, idempotency, and auth gating.

The existing suite (`test_teacher_messaging.py`) covers teacher recipients
scoping, teacher broadcast (own-students-only), the student feed, SMS flag and
preferences get/patch. Not duplicated.

Read-state is modelled as a `NotificationReadReceipt(user, notification_id)` with
`unique_together=('user','notification_id')`, and every list view computes
`isRead` from receipts filtered to `request.user`. So the security property is
per-user isolation: marking a (virtual) notification read for user A must never
flip it to read for user B. These tests lock that in end-to-end, plus the
idempotency of the mark and deny-by-default on the endpoints.
"""
from __future__ import annotations

import pytest
from django.utils import timezone
from model_bakery import baker
from rest_framework.test import APIClient

from apps.classes.models import ClassExercise
from apps.notification.models import AdminNotification, NotificationReadReceipt

pytestmark = [pytest.mark.django_db]

TEACHER_LIST = '/api/notifications/teacher/'
PREFS = '/api/notifications/preferences/'
READ_ALL = '/api/notifications/read-all/'


def _read_url(notification_id: str) -> str:
    return f'/api/notifications/{notification_id}/read/'


# ── Deny-by-default ──────────────────────────────────────────────────────────

@pytest.mark.permission
class TestAuthGating:
    def test_anonymous_cannot_mark_read(self, anon_client):
        assert anon_client.post(_read_url('admin-1')).status_code in (401, 403)

    def test_anonymous_cannot_mark_all_read(self, anon_client):
        assert anon_client.post(READ_ALL).status_code in (401, 403)

    def test_anonymous_cannot_list_teacher_feed(self, anon_client):
        assert anon_client.get(TEACHER_LIST).status_code in (401, 403)

    def test_anonymous_cannot_read_preferences(self, anon_client):
        assert anon_client.get(PREFS).status_code in (401, 403)

    def test_student_forbidden_from_teacher_feed(self, student_client):
        """The teacher feed is IsTeacherUser-gated — a student is 403."""
        assert student_client.get(TEACHER_LIST).status_code == 403


# ── Idempotency ──────────────────────────────────────────────────────────────

@pytest.mark.api
class TestMarkReadIdempotent:
    def test_marking_twice_yields_one_receipt(self, teacher_client, teacher_user):
        nid = 'admin-1'
        assert teacher_client.post(_read_url(nid)).status_code == 200
        assert teacher_client.post(_read_url(nid)).status_code == 200  # idempotent
        assert NotificationReadReceipt.objects.filter(
            user=teacher_user, notification_id=nid,
        ).count() == 1

    def test_exercise_ready_marking_twice_yields_one_receipt(self, teacher_client, teacher_user):
        session = baker.make('classes.ClassCreationSession', teacher=teacher_user)
        exercise = baker.make(
            ClassExercise,
            session=session,
            review_ready_notified_at=timezone.now(),
        )
        nid = f'exercise-ready-{exercise.id}'
        assert teacher_client.post(_read_url(nid)).status_code == 200
        assert teacher_client.post(_read_url(nid)).status_code == 200
        assert NotificationReadReceipt.objects.filter(
            user=teacher_user, notification_id=nid,
        ).count() == 1


# ── Per-user read-state isolation (the security property) ────────────────────

@pytest.mark.permission
class TestReadStateIsPerUser:
    def test_one_teacher_marking_read_does_not_affect_another(
        self, teacher_client, other_teacher_client,
    ):
        """A broadcast is visible to both teachers. Teacher A marking it read must
        leave it UNREAD for teacher B — receipts are strictly per-user."""
        notif = baker.make(AdminNotification, audience=AdminNotification.Audience.TEACHERS)
        vid = f'admin-{notif.id}'

        # Both start unread.
        a_before = teacher_client.get(TEACHER_LIST).data
        b_before = other_teacher_client.get(TEACHER_LIST).data
        assert next(i for i in a_before if i['id'] == vid)['isRead'] is False
        assert next(i for i in b_before if i['id'] == vid)['isRead'] is False

        # Teacher A marks it read.
        assert teacher_client.post(_read_url(vid)).status_code == 200

        # A now sees it read; B is unchanged (no cross-user leak).
        a_after = teacher_client.get(TEACHER_LIST).data
        b_after = other_teacher_client.get(TEACHER_LIST).data
        assert next(i for i in a_after if i['id'] == vid)['isRead'] is True
        assert next(i for i in b_after if i['id'] == vid)['isRead'] is False

    def test_read_all_creates_receipts_only_for_the_caller(
        self, teacher_client, teacher_user,
    ):
        """read-all marks the CALLER's visible notifications — never another user's."""
        baker.make(AdminNotification, audience=AdminNotification.Audience.ALL)
        baker.make(AdminNotification, audience=AdminNotification.Audience.TEACHERS)
        session = baker.make('classes.ClassCreationSession', teacher=teacher_user)
        exercise = baker.make(
            ClassExercise,
            session=session,
            review_ready_notified_at=timezone.now(),
        )
        other = baker.make('accounts.User', role='TEACHER')

        assert teacher_client.post(READ_ALL).status_code == 200
        assert NotificationReadReceipt.objects.filter(user=teacher_user).exists()
        assert NotificationReadReceipt.objects.filter(
            user=teacher_user,
            notification_id=f'exercise-ready-{exercise.id}',
        ).exists()
        # The other user got no receipts from A's read-all.
        assert not NotificationReadReceipt.objects.filter(user=other).exists()
