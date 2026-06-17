"""Organization class roster = the linked study group's students.

For an **organization** class (``session.organization`` set) that is linked to a
study group (``session.study_group`` set), the roster is owned by the org/manager,
not the teacher: the class enrolls exactly the group's ACTIVE students. Teachers
cannot hand-invite arbitrary phones into org classes (enforced in the invite view).

Because the whole student-access path is phone-based (``ClassInvitation.phone`` →
the student logs in with that phone), syncing the roster is just: make the class's
``ClassInvitation`` rows mirror the group students' phones. This reuses every
existing student endpoint unchanged.

This is pure logic (no request/response) per the services convention. The
organizations models are imported lazily to avoid an import cycle.
"""

from __future__ import annotations

import logging

from apps.classes.models import ClassCreationSession, ClassInvitation
from apps.classes.services.invite_codes import get_or_create_invite_code_for_phone

logger = logging.getLogger(__name__)


def sync_org_class_roster(session: ClassCreationSession) -> dict:
    """Make an org class's invite roster mirror its study group's active students.

    Adds a ``ClassInvitation`` for every active group student that has a phone and
    isn't invited yet; removes invites for phones no longer in the group (an org
    class roster is fully group-managed). No-op for personal classes or org
    classes without a group.

    Returns ``{'added': [...], 'removed': [...]}`` (phone lists).
    """
    if session.organization_id is None or session.study_group_id is None:
        return {'added': [], 'removed': []}

    from apps.organizations.models import StudyGroupMembership

    target_phones = {
        p.strip()
        for p in (
            StudyGroupMembership.objects
            .filter(
                study_group_id=session.study_group_id,
                status=StudyGroupMembership.Status.ACTIVE,
            )
            .values_list('student__phone', flat=True)
        )
        if p and p.strip()
    }

    existing_phones = set(
        ClassInvitation.objects.filter(session=session).values_list('phone', flat=True)
    )

    to_add = target_phones - existing_phones
    to_remove = existing_phones - target_phones

    added: list[str] = []
    for phone in sorted(to_add):
        code = get_or_create_invite_code_for_phone(phone)
        _, created = ClassInvitation.objects.get_or_create(
            session=session, phone=phone, defaults={'invite_code': code},
        )
        if created:
            added.append(phone)

    if to_remove:
        ClassInvitation.objects.filter(session=session, phone__in=to_remove).delete()

    if added or to_remove:
        logger.info(
            'Synced org class roster session=%s group=%s +%d -%d',
            session.id, session.study_group_id, len(added), len(to_remove),
        )
    return {'added': added, 'removed': sorted(to_remove)}


def sync_group_classes(study_group_id: int) -> None:
    """Re-sync every CLASS session linked to a study group.

    Called when a group's student roster changes (add/remove) so all of that
    group's classes immediately reflect the new roster.
    """
    sessions = ClassCreationSession.objects.filter(
        study_group_id=study_group_id,
        pipeline_type=ClassCreationSession.PipelineType.CLASS,
    )
    for session in sessions:
        try:
            sync_org_class_roster(session)
        except Exception:  # pragma: no cover - best-effort, never break the caller
            logger.warning('roster sync failed for session=%s', session.id, exc_info=True)
