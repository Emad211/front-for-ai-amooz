"""Model-bakery recipes for the core entities. Program: ADR-0003 (docs/testing/).

Import a recipe and call ``.make()`` (persists) or ``.prepare()`` (unsaved), or
override fields: ``student_completed.make(phone='09120000001')``. Recipes set the
DISTINGUISHING fields (role, valid phone, relationships); bakery fills the rest.
The role-authed ``APIClient`` fixtures in ``backend/conftest.py`` build on these.

Phones use ``seq`` so every STUDENT gets a unique, valid ``09XXXXXXXXX`` (the
partial ``uniq_student_phone`` constraint only allows one STUDENT per phone).
"""
from __future__ import annotations

from model_bakery.recipe import Recipe, seq

from apps.accounts.models import User
from apps.organizations.models import (
    Organization,
    OrganizationMembership,
    InvitationCode,
    StudyGroup,
)
from apps.classes.models import (
    ClassCreationSession,
    ClassSection,
    ClassUnit,
)

# --- Users (one per role) ----------------------------------------------------
# Distinct username seqs avoid the UNIQUE(username) collision across a test.
admin_user = Recipe(
    User,
    username=seq('admin_'),
    role=User.Role.ADMIN,
    is_profile_completed=True,
    is_staff=True,
    is_superuser=True,
)
teacher_user = Recipe(
    User,
    username=seq('teacher_'),
    role=User.Role.TEACHER,
    is_profile_completed=True,
)
manager_user = Recipe(
    User,
    username=seq('manager_'),
    role=User.Role.MANAGER,
    is_profile_completed=True,
)
# An onboarded student with a unique valid phone.
student_completed = Recipe(
    User,
    username=seq('student_'),
    role=User.Role.STUDENT,
    is_profile_completed=True,
    phone=seq('09120', start=100000),   # 09120100000, 09120100001, …
)
# A passwordless code-login shell (pre-onboarding); distinct phone range.
student_shell = Recipe(
    User,
    username=seq('shell_'),
    role=User.Role.STUDENT,
    is_profile_completed=False,
    phone=seq('09121', start=100000),
)

# --- Organizations / tenancy -------------------------------------------------
organization = Recipe(
    Organization,
    name=seq('Org '),
    slug=seq('org-'),
    subscription_status=Organization.SubscriptionStatus.ACTIVE,
    student_capacity=100,
)
# Pass user=… and organization=… when making these.
org_membership = Recipe(
    OrganizationMembership,
    org_role=OrganizationMembership.OrgRole.STUDENT,
    status=OrganizationMembership.MemberStatus.ACTIVE,
)
invite_code = Recipe(
    InvitationCode,
    target_role=InvitationCode.TargetRole.STUDENT,
    max_uses=30,
    is_active=True,
)
study_group = Recipe(
    StudyGroup,
    name=seq('Group '),
    status=StudyGroup.Status.ACTIVE,
)

# --- Classes domain (pass teacher=… / session=… as needed) -------------------
class_session = Recipe(
    ClassCreationSession,
    title=seq('Class '),
    pipeline_type=ClassCreationSession.PipelineType.CLASS,
    status=ClassCreationSession.Status.RECAPPED,
    is_published=True,
)
exam_prep_session = Recipe(
    ClassCreationSession,
    title=seq('Exam '),
    pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
    status=ClassCreationSession.Status.EXAM_STRUCTURED,
    is_published=True,
)
class_section = Recipe(
    ClassSection,
    title=seq('Section '),
    external_id=seq('sec-'),
)
class_unit = Recipe(
    ClassUnit,
    title=seq('Unit '),
    external_id=seq('unit-'),
)
