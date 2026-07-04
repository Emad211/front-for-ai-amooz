"""FK on_delete behavior for ClassCreationSession and its children.

`test_model_constraints.py` covers unique/partial constraints, choices and index
presence — but NOT what happens on delete. That distinction is load-bearing:
* `organization` and `study_group` are **SET_NULL** — deleting an org (or a study
  group) must leave the teacher's class intact with a nulled FK, NOT cascade-
  destroy the class;
* `teacher` and every session-child (invitations, sections, units) are **CASCADE**
  — deleting the session (or teacher) tears the owned graph down cleanly.

A regression that flipped organization from SET_NULL to CASCADE would silently
delete every class in an org when the org is removed — this locks it.
"""
from __future__ import annotations

import pytest
from model_bakery import baker

from apps.accounts.models import User
from apps.classes.models import (
    ClassCreationSession,
    ClassInvitation,
    ClassSection,
    ClassUnit,
)
from apps.organizations.models import Organization, StudyGroup

pytestmark = [pytest.mark.django_db, pytest.mark.unit]


def _session(**kw):
    return baker.make(ClassCreationSession, pipeline_type='class', **kw)


class TestSetNullPreservesTheClass:
    def test_deleting_organization_nulls_fk_but_keeps_session(self):
        org = baker.make(Organization)
        session = _session(organization=org)
        org.delete()
        session.refresh_from_db()
        assert ClassCreationSession.objects.filter(id=session.id).exists()
        assert session.organization_id is None  # SET_NULL, not CASCADE

    def test_deleting_study_group_nulls_fk_but_keeps_session(self):
        org = baker.make(Organization)
        group = baker.make(StudyGroup, organization=org)
        session = _session(organization=org, study_group=group)
        group.delete()
        session.refresh_from_db()
        assert ClassCreationSession.objects.filter(id=session.id).exists()
        assert session.study_group_id is None  # SET_NULL


class TestCascadeTearsDownOwnedGraph:
    def test_deleting_session_cascades_invitations(self):
        session = _session()
        baker.make(ClassInvitation, session=session, phone='09121111111', invite_code='C1')
        baker.make(ClassInvitation, session=session, phone='09122222222', invite_code='C2')
        session.delete()
        assert not ClassInvitation.objects.filter(session_id=session.id).exists()

    def test_deleting_session_cascades_sections_and_units(self):
        session = _session()
        section = baker.make(ClassSection, session=session)
        baker.make(ClassUnit, session=session, section=section)
        sec_id, sess_id = section.id, session.id
        session.delete()
        assert not ClassSection.objects.filter(id=sec_id).exists()
        assert not ClassUnit.objects.filter(session_id=sess_id).exists()

    def test_deleting_section_cascades_its_units(self):
        session = _session()
        section = baker.make(ClassSection, session=session)
        unit = baker.make(ClassUnit, session=session, section=section)
        section.delete()
        assert not ClassUnit.objects.filter(id=unit.id).exists()
        # The session itself is untouched by a section delete.
        assert ClassCreationSession.objects.filter(id=session.id).exists()

    def test_deleting_teacher_cascades_their_sessions(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        session = _session(teacher=teacher)
        sid = session.id
        teacher.delete()
        assert not ClassCreationSession.objects.filter(id=sid).exists()
