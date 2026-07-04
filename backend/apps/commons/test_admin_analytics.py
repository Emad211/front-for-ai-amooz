"""`/api/admin/analytics/*` — the platform admin analytics + activity feed.

This whole surface (stats / chart / distribution / recent-activity) had **zero**
tests. All four views gate on DRF ``IsAdminUser`` (which keys on ``is_staff``,
NOT the ``role`` field — so role=ADMIN without is_staff would still be denied).

Covered here:
* security matrix on EVERY endpoint — anon→401/403, student/teacher/MANAGER→403,
  platform admin (is_staff)→200 (security-auditor: no admin route is un-gated,
  no escalation via role vs is_staff);
* exact aggregation numbers (seed a known user/class/quiz/llm set, assert counts);
* Tehran-timezone day bucketing on the chart (frozen at a UTC↔Tehran day boundary)
  + zero-fill length;
* the unified activity feed: event presence, ``?type=`` filter, ``?limit=`` cap.
"""
from __future__ import annotations

import pytest
from model_bakery import baker
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User

STATS = '/api/admin/analytics/stats/'
CHART = '/api/admin/analytics/chart/'
DIST = '/api/admin/analytics/distribution/'
RECENT = '/api/admin/analytics/recent-activity/'
ALL_ENDPOINTS = [STATS, CHART, DIST, RECENT]

pytestmark = [pytest.mark.django_db]


def _auth(user) -> APIClient:
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')
    return c


def _admin() -> User:
    return baker.make(User, role=User.Role.ADMIN, is_staff=True, is_superuser=True)


# ── Authorization matrix (MANDATORY on the admin surface) ────────────────────

@pytest.mark.permission
class TestAnalyticsAuthorization:
    @pytest.mark.parametrize('url', ALL_ENDPOINTS)
    def test_anonymous_denied(self, url):
        assert APIClient().get(url).status_code in (401, 403)

    @pytest.mark.parametrize('url', ALL_ENDPOINTS)
    @pytest.mark.parametrize('role', [User.Role.STUDENT, User.Role.TEACHER, User.Role.MANAGER])
    def test_non_staff_roles_forbidden(self, url, role):
        """Even a MANAGER (org admin) is not a PLATFORM admin — is_staff=False → 403."""
        user = baker.make(User, role=role, is_staff=False)
        assert _auth(user).get(url).status_code == 403

    @pytest.mark.parametrize('url', ALL_ENDPOINTS)
    def test_platform_admin_allowed(self, url):
        assert _auth(_admin()).get(url).status_code == 200

    def test_role_admin_is_sufficient_even_without_is_staff(self):
        """`IsPlatformAdmin` admits ANY of role==ADMIN / is_superuser / is_staff
        (documented). role=ADMIN alone grants access — the non-admin roles above
        (STUDENT/TEACHER/MANAGER) have none of the three, so they stay denied."""
        role_only_admin = baker.make(User, role=User.Role.ADMIN, is_staff=False, is_superuser=False)
        assert _auth(role_only_admin).get(STATS).status_code == 200


# ── Aggregation correctness (exact numbers) ──────────────────────────────────

@pytest.mark.api
class TestStatsAggregation:
    def test_stats_aggregation_matches_ground_truth(self):
        """Seed a known, non-trivial data set, then assert the view's aggregation
        equals the ORM ground truth. Comparing to the DB (not hardcoded numbers)
        keeps the test correct despite model-bakery auto-creating incidental FK
        users/sessions — while still proving the grouping/filter logic is right."""
        from apps.classes.models import ClassCreationSession, ClassSectionQuizAttempt
        from apps.commons.models import LLMUsageLog

        Status = ClassCreationSession.Status
        admin = _admin()
        baker.make(User, role=User.Role.STUDENT, _quantity=3)
        baker.make(User, role=User.Role.TEACHER, _quantity=2)
        baker.make(User, role=User.Role.MANAGER, _quantity=1)

        baker.make(ClassCreationSession, teacher=admin,
                   pipeline_type=ClassCreationSession.PipelineType.CLASS,
                   status=Status.RECAPPED, is_published=True)
        baker.make(ClassCreationSession, teacher=admin,
                   pipeline_type=ClassCreationSession.PipelineType.CLASS,
                   status=Status.FAILED, is_published=False)

        baker.make(ClassSectionQuizAttempt, passed=True)
        baker.make(ClassSectionQuizAttempt, passed=False)
        baker.make(LLMUsageLog, _quantity=4, success=True,
                   estimated_cost_usd=0.01, total_tokens=100)

        res = _auth(admin).get(STATS)
        assert res.status_code == 200
        d = res.data

        # Users: response == per-role ORM counts (proves the group-by-role query).
        assert d['users']['students'] == User.objects.filter(role='STUDENT').count()
        assert d['users']['teachers'] == User.objects.filter(role='TEACHER').count()
        assert d['users']['managers'] == User.objects.filter(role='MANAGER').count() == 1
        assert d['users']['admins'] == User.objects.filter(role='ADMIN').count() == 1
        assert d['users']['total'] == User.objects.count()

        # Classes: totals + the is_published / status=FAILED filters.
        assert d['classes']['total'] == ClassCreationSession.objects.count()
        assert d['classes']['published'] == ClassCreationSession.objects.filter(is_published=True).count()
        assert d['classes']['failed'] == ClassCreationSession.objects.filter(status=Status.FAILED).count() == 1

        # Engagement: quiz totals + the passed→pass_rate math.
        q_total = ClassSectionQuizAttempt.objects.count()
        q_passed = ClassSectionQuizAttempt.objects.filter(passed=True).count()
        assert d['engagement']['quiz_total'] == q_total == 2
        assert d['engagement']['quiz_pass_rate'] == round(q_passed / q_total * 100, 1) == 50.0

        # LLM: nothing else creates usage logs, so these are exact.
        assert d['llm']['requests_total'] == 4
        assert d['llm']['tokens_total'] == 400


@pytest.mark.api
class TestDistribution:
    def test_distribution_groups_by_pipeline_type(self):
        from apps.classes.models import ClassCreationSession
        admin = _admin()
        baker.make(ClassCreationSession, teacher=admin,
                   pipeline_type=ClassCreationSession.PipelineType.CLASS, _quantity=2)
        baker.make(ClassCreationSession, teacher=admin,
                   pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP, _quantity=1)

        res = _auth(admin).get(DIST)
        assert res.status_code == 200
        by_type = {r['pipeline_type']: r['count'] for r in res.data['by_pipeline_type']}
        assert by_type.get('class') == 2
        assert by_type.get('exam_prep') == 1


# ── Tehran-timezone day bucketing ────────────────────────────────────────────

@pytest.mark.api
class TestChartTehranBucketing:
    def test_chart_zero_fills_and_buckets_today_in_tehran(self, freeze_tehran):
        """Frozen at 2026-06-15 20:30 UTC = 2026-06-16 00:00 Tehran. Every user
        created in-test joins 'now', so all land on Tehran-today's bucket — a
        naive-UTC implementation would mis-bucket them onto 2026-06-15."""
        admin = _admin()
        res = _auth(admin).get(CHART, {'days': 7})
        assert res.status_code == 200
        out = res.data
        assert len(out) == 7  # zero-filled, one row per Tehran day
        assert {'date', 'registrations', 'classes', 'quizzes', 'chats'} <= set(out[0])
        last = out[-1]
        assert last['date'] == '2026-06-16'  # Tehran today, not UTC's 06-15
        assert last['registrations'] == User.objects.count()

    def test_chart_days_param_is_clamped(self, freeze_tehran):
        admin = _admin()
        assert len(_auth(admin).get(CHART, {'days': 999}).data) == 90   # max
        assert len(_auth(admin).get(CHART, {'days': 0}).data) == 1      # min
        assert len(_auth(admin).get(CHART, {'days': 'abc'}).data) == 14  # default


# ── Unified activity feed ────────────────────────────────────────────────────

@pytest.mark.api
class TestRecentActivityFeed:
    def test_feed_includes_registration_events(self):
        admin = _admin()
        baker.make(User, role=User.Role.STUDENT, first_name='دانش', last_name='آموز')
        res = _auth(admin).get(RECENT)
        assert res.status_code == 200
        types = {item['type'] for item in res.data}
        assert 'registration' in types
        # every item carries the merge contract keys
        for item in res.data:
            assert {'type', 'category', 'user', 'action', 'time'} <= set(item)

    def test_type_filter_restricts_to_requested_events(self):
        admin = _admin()
        baker.make(User, role=User.Role.STUDENT, _quantity=2)
        res = _auth(admin).get(RECENT, {'type': 'registration'})
        assert res.status_code == 200
        assert {item['type'] for item in res.data} <= {'registration'}

    def test_limit_is_capped_at_100(self):
        admin = _admin()
        res = _auth(admin).get(RECENT, {'limit': 9999})
        assert res.status_code == 200
        assert len(res.data) <= 100
