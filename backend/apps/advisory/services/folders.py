"""The write door for advisor-owned student folders (risman step 1, گام ۱).

``AdvisoryStudentFolder`` is tenancy-bearing, so every mutation goes through
this one module after the view has resolved ownership — the folder itself via
``get_folder`` (advisor-scoped lookup) and the engagement via
``scope.advisor_engagement``. The exact Persian validation messages are this
module's contract; serializers stay shape-only so the wire errors never drift
from here.

The rules that live here and nowhere else:

* A folder name is required (blank/whitespace rejected), at most
  ``MAX_FOLDER_NAME_CHARS`` characters, and unique per advisor — the duplicate
  check runs ahead of the DB constraint so the wire answers a 400 with the
  pinned message instead of an ``IntegrityError`` 500.
* Deleting a folder nulls ``engagement.folder`` for every engagement inside it
  **in the same transaction** as the delete (ق۷): the roster rows survive,
  they simply fall back to «بدون پوشه».
"""

from __future__ import annotations

from django.db import transaction
from django.db.models import Q, QuerySet

from ..models import MAX_FOLDER_NAME_CHARS, AdvisoryEngagement, AdvisoryStudentFolder

# Pinned wire messages (byte-for-byte contract with the frontend).
MSG_NAME_REQUIRED = 'نام پوشه الزامی است.'
MSG_NAME_TOO_LONG = 'نام پوشه حداکثر ۶۴ نویسه است.'
MSG_DUPLICATE = 'پوشه‌ای با این نام دارید.'


class FolderError(Exception):
    """400-family validation error; ``str(exc)`` is the Persian wire message."""


def _fail(message: str) -> None:
    raise FolderError(message)


def _clean_name(name) -> str:
    """Validate one folder name against the pinned rules; return it trimmed."""
    if not isinstance(name, str) or not name.strip():
        _fail(MSG_NAME_REQUIRED)
    cleaned = name.strip()
    if len(cleaned) > MAX_FOLDER_NAME_CHARS:
        _fail(MSG_NAME_TOO_LONG)
    return cleaned


def list_folders(advisor) -> QuerySet[AdvisoryStudentFolder]:
    """The advisor's own folders, name order.

    A non-advisor gets an empty queryset rather than an exception, mirroring
    ``scope.visible_engagements`` — views already answer 403 through
    ``IsAdvisorUser``, so a silent ``.none()`` leaks nothing even if a future
    caller forgets the permission class.
    """
    role = getattr(advisor, 'role', None)
    if not getattr(advisor, 'is_authenticated', False) or role != 'ADVISOR':
        return AdvisoryStudentFolder.objects.none()
    return AdvisoryStudentFolder.objects.filter(advisor=advisor).order_by('name', 'id')


def get_folder(advisor, folder_id) -> AdvisoryStudentFolder | None:
    """One folder of *this* advisor, or ``None`` — never another advisor's.

    The per-id sibling of ``list_folders``, shaped like
    ``scope.advisor_engagement``: a foreign row and a nonexistent id are
    indistinguishable here, which is what lets the view answer both with a
    404 instead of a 403 that would confirm existence.
    """
    role = getattr(advisor, 'role', None)
    if not getattr(advisor, 'is_authenticated', False) or role != 'ADVISOR':
        return None
    return AdvisoryStudentFolder.objects.filter(advisor=advisor, pk=folder_id).first()


def create_folder(advisor, name) -> AdvisoryStudentFolder:
    """Create one folder owned by ``advisor`` under the uniqueness rule."""
    cleaned = _clean_name(name)
    if AdvisoryStudentFolder.objects.filter(advisor=advisor, name=cleaned).exists():
        _fail(MSG_DUPLICATE)
    return AdvisoryStudentFolder.objects.create(advisor=advisor, name=cleaned)


def rename_folder(folder: AdvisoryStudentFolder, name) -> AdvisoryStudentFolder:
    """Rename one already-resolved folder under the same uniqueness rule."""
    cleaned = _clean_name(name)
    duplicate = (
        AdvisoryStudentFolder.objects.filter(
            advisor_id=folder.advisor_id, name=cleaned,
        )
        .exclude(pk=folder.pk)
        .exists()
    )
    if duplicate:
        _fail(MSG_DUPLICATE)
    folder.name = cleaned
    folder.save(update_fields=['name'])
    return folder


def delete_folder(folder: AdvisoryStudentFolder) -> None:
    """Remove one folder outright; its engagements keep existing, unfiled."""
    with transaction.atomic():
        AdvisoryEngagement.objects.filter(folder=folder).update(folder=None)
        folder.delete()


def assign_engagement_folder(engagement, folder) -> None:
    """Attach one already-resolved engagement to a folder (or detach with None).

    Both arguments arrive ownership-proven (engagement via
    ``scope.advisor_engagement``, folder via ``get_folder``), so this is a pure
    setter — the tenancy checks live where they can see the URL, not here.
    """
    engagement.folder = folder
    engagement.save(update_fields=['folder'])


def filter_roster(roster: QuerySet[AdvisoryEngagement], *, q=None, folder=None):
    """Apply the risman step-1 roster filters onto an already-scoped queryset.

    ``q`` is an icontains needle OR-combined across the student's first name,
    last name, username and phone. ``folder`` is a resolved folder instance;
    passing both narrows to their intersection. The queryset must come from
    ``scope.advisor_students`` — this function adds filters only, never scope.
    """
    filtered = roster
    if q:
        needle = q.strip()
        if needle:
            filtered = filtered.filter(
                Q(student__first_name__icontains=needle)
                | Q(student__last_name__icontains=needle)
                | Q(student__username__icontains=needle)
                | Q(student__phone__icontains=needle)
            )
    if folder is not None:
        filtered = filtered.filter(folder_id=folder.pk)
    return filtered
