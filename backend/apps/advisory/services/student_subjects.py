"""The write door for a student's subject selection (S4).

``StudentSubject`` is tenancy-bearing, so — exactly like ``invites.py`` for the
engagement itself — every mutation of it goes through this one module, never
through a view. The split from ``scope.py`` mirrors the invite split: ``scope``
reads across tenancy, this constructs it.

There is one public function, ``set_engagement_subjects``. It is a **set-replace**,
not an append: the caller sends the complete list of subjects a student should
have, and the store is made to match it. "Made to match" means toggling
``is_active`` — never deleting a row — so a subject removed today and re-added
next week is the same row with its history intact, and a plan (step 8) that
pointed at it never dangles.

Authorization lives one layer up: the view resolves the engagement through
``scope.advisor_engagement`` (404 if foreign) before calling in here, and the
subject ids are validated against ``scope.curriculum_subjects`` — the national
curriculum the *student's* own (grade, major) derives — below. This module
assumes the engagement is already the advisor's; it does not re-derive ownership.
"""

from __future__ import annotations

from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from ..models import StudentSubject
from . import scope

# A defensive ceiling on one write. The picker offers a curated catalog, not free
# text, so a real request is a handful of subjects; anything past this is a script.
# ``EngagementSubjectsWriteSerializer`` imports this constant and enforces it, so
# the value lives next to the store it protects and there is exactly one of it.
MAX_SUBJECTS_PER_STUDENT = 60


class SubjectSelectionError(Exception):
    """Base class so a view can catch the whole family in one clause."""


class SubjectNotAssignable(SubjectSelectionError):
    """400 — the body named a subject outside this student's derived curriculum.

    "Not in the curriculum" folds together the cases the caller must not be able to
    tell apart: the id does not exist, it is deactivated, it belongs to another
    grade or major than the student's own, or it is an organization-private subject
    of an org the student does not belong to. All are "not derivable for this
    student", and distinguishing them would leak both other majors' catalogs and
    other organizations' private ones.
    """

    def __init__(self, subject_ids):
        self.subject_ids = list(subject_ids)
        super().__init__(
            'این درس در برنامه‌ی درسیِ این دانش‌آموز نیست.'
        )


def set_engagement_subjects(engagement, subject_ids, *, advisor) -> QuerySet[StudentSubject]:
    """Make the engagement's active subject set equal ``subject_ids`` exactly.

    ``subject_ids`` is de-duplicated first; assignability is checked **before** any
    write, so a request naming one foreign subject changes nothing at all (it
    raises ``SubjectNotAssignable`` and the transaction never opens). Then, in one
    transaction:

    * every wanted subject is activated — ``get_or_create`` reuses the existing row
      for a previously-removed subject and flips it back on, so re-adding is not a
      new row;
    * every currently-active row **not** in the wanted set is deactivated.

    An empty ``subject_ids`` is legal and means "clear the selection": nothing is
    activated and all active rows are switched off. Returns the resulting active
    set (through ``scope.student_subjects`` — the same shape the read path uses).

    ``advisor`` is retained on the signature (the view still passes ``request.user``)
    for call-site stability and to document who is acting, but assignability is now
    a fact about the *student's* curriculum, not the advisor's org catalog — so the
    validation set comes from ``scope.curriculum_subjects(engagement.student)``.
    """
    wanted = list(dict.fromkeys(int(s) for s in subject_ids))

    if wanted:
        assignable = set(
            scope.curriculum_subjects(engagement.student)
            .filter(pk__in=wanted)
            .values_list('pk', flat=True)
        )
        foreign = [sid for sid in wanted if sid not in assignable]
        if foreign:
            raise SubjectNotAssignable(foreign)

    with transaction.atomic():
        for sid in wanted:
            row, created = StudentSubject.objects.get_or_create(
                engagement=engagement,
                subject_id=sid,
                defaults={'is_active': True},
            )
            if not created and not row.is_active:
                row.is_active = True
                row.save(update_fields=['is_active', 'updated_at'])

        (
            StudentSubject.objects.filter(engagement=engagement, is_active=True)
            .exclude(subject_id__in=wanted)
            .update(is_active=False, updated_at=timezone.now())
        )

    return scope.student_subjects(engagement)
