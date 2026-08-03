"""Authorization-aware organization and study-group scope for Exam Prep V4."""
from __future__ import annotations

from dataclasses import dataclass

from apps.organizations.models import (
    Organization,
    OrganizationMembership,
    StudyGroup,
    StudyGroupTeacher,
)


class ExamPrepV4ScopeError(PermissionError):
    pass


@dataclass(frozen=True, slots=True)
class ResolvedExamScope:
    organization: Organization | None
    study_group: StudyGroup | None


def resolve_exam_scope(
    *,
    user,
    organization_id: int | None = None,
    study_group_id: int | None = None,
) -> ResolvedExamScope:
    """Resolve a personal or organization scope without leaking inaccessible rows."""

    if organization_id is None and study_group_id is None:
        return ResolvedExamScope(organization=None, study_group=None)

    study_group = None
    if study_group_id is not None:
        study_group = (
            StudyGroup.objects.select_related('organization')
            .filter(id=study_group_id, is_active=True)
            .first()
        )
        if study_group is None:
            raise ExamPrepV4ScopeError('Study group is unavailable.')
        if organization_id is None:
            organization_id = study_group.organization_id
        elif study_group.organization_id != organization_id:
            raise ExamPrepV4ScopeError(
                'Study group does not belong to the selected organization.'
            )

    organization = Organization.objects.filter(
        id=organization_id,
        is_active=True,
    ).first()
    if organization is None:
        raise ExamPrepV4ScopeError('Organization is unavailable.')

    is_owner = organization.owner_id == user.id
    membership = (
        OrganizationMembership.objects.filter(
            organization=organization,
            user=user,
            is_active=True,
        )
        .only('id', 'role')
        .first()
    )
    allowed_roles = {
        OrganizationMembership.OrgRole.ADMIN,
        OrganizationMembership.OrgRole.DEPUTY,
        OrganizationMembership.OrgRole.TEACHER,
    }
    if not is_owner and (membership is None or membership.role not in allowed_roles):
        raise ExamPrepV4ScopeError('Organization is unavailable.')

    if study_group is not None and not is_owner:
        assert membership is not None
        if membership.role == OrganizationMembership.OrgRole.TEACHER:
            assigned = StudyGroupTeacher.objects.filter(
                study_group=study_group,
                teacher=user,
                is_active=True,
            ).exists()
            if not assigned:
                raise ExamPrepV4ScopeError('Study group is unavailable.')

    return ResolvedExamScope(
        organization=organization,
        study_group=study_group,
    )
