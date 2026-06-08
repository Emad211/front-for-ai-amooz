"""Tests for per-organization / per-study-group LLM cost attribution.

Covers:
  * ``track_llm_usage`` denormalizes (organization_id, study_group_id) from the
    class session at write time.
  * Personal/freelancer classes get no org attribution.
  * The org-scoped ``/costs/`` endpoint rolls up by teacher + study group.
  * Org admin permission gating on that endpoint.
  * The platform-admin flexible breakdown supports ``group_by=organization``.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient

from apps.classes.models import ClassCreationSession
from apps.commons.models import LLMUsageLog
from apps.commons.token_tracker import track_llm_usage
from apps.organizations.models import (
    Organization,
    OrganizationMembership,
    StudyGroup,
)

User = get_user_model()
pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _user(username, role=User.Role.TEACHER, **kw):
    return User.objects.create_user(username=username, password='p', role=role, **kw)


def _org(name='Org', slug='org'):
    return Organization.objects.create(name=name, slug=slug)


def _group(org, name='دهم ریاضی', **kw):
    return StudyGroup.objects.create(organization=org, name=name, **kw)


def _class(teacher, *, organization=None, study_group=None):
    """Minimal valid ClassCreationSession for attribution tests."""
    return ClassCreationSession.objects.create(
        teacher=teacher,
        organization=organization,
        study_group=study_group,
        title='درس تست',
        source_file=SimpleUploadedFile('a.mp3', b'x'),
        source_mime_type='audio/mpeg',
        source_original_name='a.mp3',
        status=ClassCreationSession.Status.RECAPPED,
    )


def _fake_resp(prompt=100, completion=50):
    """An OpenAI/Avalai-shaped response object with a usage block."""
    return SimpleNamespace(
        usage=SimpleNamespace(
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=prompt + completion,
        )
    )


def _log(*, user=None, organization=None, study_group=None, cost_toman=1000, tokens=150):
    """Create an LLMUsageLog row directly (bypasses the tracker)."""
    return LLMUsageLog.objects.create(
        user=user,
        feature=LLMUsageLog.Feature.OTHER if hasattr(LLMUsageLog.Feature, 'OTHER') else 'other',
        provider='avalai',
        model_name='gpt-test',
        input_tokens=tokens,
        output_tokens=0,
        total_tokens=tokens,
        estimated_cost_usd=0,
        estimated_cost_toman=cost_toman,
        usd_toman_rate=60000,
        organization=organization,
        study_group=study_group,
    )


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Never hit the exchange-rate API during tracking tests."""
    monkeypatch.setattr(
        'apps.commons.token_tracker.convert_usd_to_toman',
        lambda usd: (float(usd) * 60000.0, 60000.0, None),
    )


# ---------------------------------------------------------------------------
# write-time attribution
# ---------------------------------------------------------------------------

def test_usage_is_attributed_to_org_and_group():
    teacher = _user('t1')
    org = _org()
    group = _group(org)
    session = _class(teacher, organization=org, study_group=group)

    log = track_llm_usage(
        resp=_fake_resp(),
        feature='other',
        provider='avalai',
        model_name='gpt-test',
        user=teacher,
        session_id=session.id,
    )

    assert log is not None
    assert log.organization_id == org.id
    assert log.study_group_id == group.id
    assert log.session_id == session.id


def test_personal_class_has_no_org_attribution():
    teacher = _user('freelancer')
    session = _class(teacher)  # no org / no group

    log = track_llm_usage(
        resp=_fake_resp(),
        feature='other',
        provider='avalai',
        model_name='gpt-test',
        user=teacher,
        session_id=session.id,
    )

    assert log is not None
    assert log.organization_id is None
    assert log.study_group_id is None


def test_usage_without_session_has_no_org():
    teacher = _user('t2')
    log = track_llm_usage(
        resp=_fake_resp(),
        feature='other',
        provider='avalai',
        model_name='gpt-test',
        user=teacher,
        session_id=None,
    )
    assert log is not None
    assert log.organization_id is None and log.study_group_id is None


# ---------------------------------------------------------------------------
# org-scoped /costs/ endpoint
# ---------------------------------------------------------------------------

def _costs_url(org):
    return f'/api/organizations/{org.id}/costs/'


def test_org_costs_endpoint_breaks_down_by_teacher_and_group():
    org = _org()
    other_org = _org(name='Other', slug='other')
    admin = _user('admin1')
    OrganizationMembership.objects.create(
        organization=org, user=admin, org_role=OrganizationMembership.OrgRole.ADMIN
    )
    t1 = _user('teach1')
    t2 = _user('teach2')
    g_math = _group(org, name='دهم ریاضی')
    g_phys = _group(org, name='یازدهم فیزیک')

    # org rows: t1 → math 2000, t2 → phys 1500
    _log(user=t1, organization=org, study_group=g_math, cost_toman=2000)
    _log(user=t2, organization=org, study_group=g_phys, cost_toman=1500)
    # noise that must NOT count: another org + a purely-personal row
    _log(user=t1, organization=other_org, study_group=None, cost_toman=9999)
    _log(user=t1, organization=None, study_group=None, cost_toman=8888)

    client = APIClient()
    client.force_authenticate(user=admin)
    res = client.get(_costs_url(org), {'days': 30})

    assert res.status_code == 200
    body = res.data
    assert body['summary']['totalCostToman'] == 3500
    assert body['summary']['totalRequests'] == 2

    by_teacher = {row['teacherId']: row['costToman'] for row in body['byTeacher']}
    assert by_teacher == {t1.id: 2000, t2.id: 1500}

    by_group = {row['studyGroupId']: row['costToman'] for row in body['byStudyGroup']}
    assert by_group == {g_math.id: 2000, g_phys.id: 1500}


def test_org_costs_endpoint_forbidden_for_non_admin():
    org = _org()
    teacher = _user('plain')
    OrganizationMembership.objects.create(
        organization=org, user=teacher, org_role=OrganizationMembership.OrgRole.TEACHER
    )
    client = APIClient()
    client.force_authenticate(user=teacher)
    res = client.get(_costs_url(org))
    assert res.status_code == 403


def test_org_costs_endpoint_requires_auth():
    org = _org()
    res = APIClient().get(_costs_url(org))
    assert res.status_code in (401, 403)


# ---------------------------------------------------------------------------
# platform-admin flexible breakdown by organization
# ---------------------------------------------------------------------------

def test_admin_breakdown_group_by_organization():
    org = _org()
    staff = _user('staff', role=User.Role.ADMIN, is_staff=True)
    t1 = _user('teachX')
    _log(user=t1, organization=org, study_group=None, cost_toman=1200)
    _log(user=t1, organization=None, study_group=None, cost_toman=300)  # personal

    client = APIClient()
    client.force_authenticate(user=staff)
    res = client.get('/api/admin/llm-usage/breakdown/', {'group_by': 'organization', 'days': 365})

    assert res.status_code == 200
    assert res.data['group_by'] == ['organization']
    by_org = {row.get('organization_id'): row for row in res.data['results']}
    assert by_org[org.id]['total_cost_toman'] == 1200
    # personal rows bucket under the null org with the Persian label
    assert by_org[None]['organization_name'] == '— شخصی —'
    assert by_org[None]['total_cost_toman'] == 300


# ---------------------------------------------------------------------------
# self-service: a teacher's OWN personal/freelancer usage
# ---------------------------------------------------------------------------

_MY_USAGE_URL = '/api/classes/teacher/my-ai-usage/'


def test_my_usage_shows_only_personal_usage():
    org = _org()
    me = _user('freelancer')
    other = _user('someone_else')
    # my personal usage (org null) — counts
    _log(user=me, organization=None, study_group=None, cost_toman=500, tokens=100)
    _log(user=me, organization=None, study_group=None, cost_toman=300, tokens=80)
    # my org-attributed usage — billed to org, excluded from my personal view
    _log(user=me, organization=org, study_group=None, cost_toman=9999, tokens=999)
    # another user's personal usage — excluded
    _log(user=other, organization=None, study_group=None, cost_toman=7777, tokens=700)

    client = APIClient()
    client.force_authenticate(user=me)
    res = client.get(_MY_USAGE_URL, {'days': 30})

    assert res.status_code == 200
    assert res.data['summary']['totalCostToman'] == 800
    assert res.data['summary']['totalRequests'] == 2
    assert res.data['summary']['totalTokens'] == 180
    assert isinstance(res.data['byFeature'], list)
    assert isinstance(res.data['daily'], list)


def test_my_usage_requires_auth():
    res = APIClient().get(_MY_USAGE_URL)
    assert res.status_code in (401, 403)
