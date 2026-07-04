"""Smoke test for the shared fixture/recipe layer (ADR-0003, T3).

Proves the recipes build valid objects and the role-authed clients + mock_llm +
freeze_tehran fixtures work — so per-app steps can reuse them with confidence.
"""
import pytest

from apps.accounts.models import User

pytestmark = pytest.mark.unit


def test_role_user_fixtures_have_expected_roles(admin_user, teacher_user, manager_user, student_user, student_shell):
    assert admin_user.role == User.Role.ADMIN and admin_user.is_staff and admin_user.is_superuser
    assert teacher_user.role == User.Role.TEACHER
    assert manager_user.role == User.Role.MANAGER
    assert student_user.role == User.Role.STUDENT and student_user.is_profile_completed is True
    assert student_shell.role == User.Role.STUDENT and student_shell.is_profile_completed is False


def test_students_get_unique_valid_phones(db):
    from testing.recipes import student_completed
    s1 = student_completed.make()
    s2 = student_completed.make()
    for s in (s1, s2):
        assert s.phone.startswith('09') and len(s.phone) == 11 and s.phone.isdigit()
    assert s1.phone != s2.phone  # the partial uniq_student_phone constraint holds


def test_org_recipes_build(db):
    from testing.recipes import organization, org_membership, invite_code, study_group, teacher_user
    org = organization.make()
    assert org.slug and org.subscription_status == 'active'
    t = teacher_user.make()
    m = org_membership.make(user=t, organization=org)
    assert m.organization_id == org.id and m.user_id == t.id
    code = invite_code.make(organization=org, created_by=t)
    assert code.code and code.organization_id == org.id
    group = study_group.make(organization=org, created_by=t)
    assert group.organization_id == org.id


def test_class_session_recipe_builds(db):
    from testing.recipes import class_session, exam_prep_session, teacher_user
    t = teacher_user.make()
    cs = class_session.make(teacher=t)
    assert cs.pipeline_type == 'class' and cs.teacher_id == t.id
    eps = exam_prep_session.make(teacher=t)
    assert eps.pipeline_type == 'exam_prep'


def test_authed_clients_authenticate(admin_client, teacher_client, student_client, manager_client, anon_client):
    # A trivial authenticated GET returns the caller's profile; anon is 401.
    for client in (admin_client, teacher_client, student_client, manager_client):
        resp = client.get('/api/accounts/me/')
        assert resp.status_code == 200
    assert anon_client.get('/api/accounts/me/').status_code == 401


def test_wrong_owner_clients_are_distinct(teacher_client, other_teacher_client):
    a = teacher_client.get('/api/accounts/me/').json()
    b = other_teacher_client.get('/api/accounts/me/').json()
    assert a['id'] != b['id']


def test_mock_llm_patches_stage_generate_text(mock_llm):
    from types import SimpleNamespace
    from apps.classes.services import exam_prep_structure as eps
    mock_llm.return_value = SimpleNamespace(text='{"exam_prep": {"questions": []}}')
    # Calling the patched name returns the canned value without hitting the gateway.
    assert eps.generate_text(messages=[]).text == '{"exam_prep": {"questions": []}}'
    assert mock_llm.call_count == 1


def test_freeze_tehran_pins_time(freeze_tehran):
    from django.utils import timezone
    # 2026-06-15 20:30 UTC is frozen.
    assert timezone.now().year == 2026 and timezone.now().hour == 20
