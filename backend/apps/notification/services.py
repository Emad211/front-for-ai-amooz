"""Helpers for teacher-scoped messaging.

A teacher's "students" are the distinct phone numbers invited to any of that
teacher's class/exam sessions (excluding the teacher's own phone). These helpers
both power the recipient picker and enforce that a teacher can only message
their own students.
"""
from __future__ import annotations

from apps.accounts.models import User
from apps.classes.models import Enrollment, TeacherStudentAccess


def student_teacher_ids(*, student) -> set[int]:
    """Teachers who currently have a real enrollment relationship with a student."""
    suspended_teacher_ids = TeacherStudentAccess.objects.filter(
        student=student,
        is_suspended=True,
    ).values('teacher_id')
    personal = Enrollment.objects.filter(
        student=student,
        session__organization__isnull=True,
    ).exclude(session__teacher_id__in=suspended_teacher_ids)
    organization = Enrollment.objects.filter(
        student=student,
        session__organization__isnull=False,
    )
    return set(
        (personal | organization)
        .values_list('session__teacher_id', flat=True)
        .distinct()
    )


def teacher_student_phones(*, teacher) -> set[str]:
    """Set of distinct student phone numbers across the teacher's sessions."""
    suspended_ids = TeacherStudentAccess.objects.filter(
        teacher=teacher, is_suspended=True,
    ).values('student_id')
    personal = Enrollment.objects.filter(
        session__teacher=teacher,
        session__organization__isnull=True,
    ).exclude(student_id__in=suspended_ids)
    organization = Enrollment.objects.filter(
        session__teacher=teacher,
        session__organization__isnull=False,
    )
    phones = set()
    for p in (
        (personal | organization)
        .values_list('student__phone', flat=True)
        .distinct()
    ):
        norm = (p or '').strip()
        if norm:
            phones.add(norm)
    return phones


def teacher_student_recipients(*, teacher) -> list[dict]:
    """Recipient picker rows for the teacher's students (resolves real names)."""
    phones = sorted(teacher_student_phones(teacher=teacher))
    users_by_phone: dict[str, User] = {}
    if phones:
        for u in User.objects.filter(phone__in=phones).only(
            'id', 'first_name', 'last_name', 'username', 'email', 'phone'
        ):
            p = (getattr(u, 'phone', None) or '').strip()
            if p:
                users_by_phone[p] = u

    out: list[dict] = []
    for phone in phones:
        u = users_by_phone.get(phone)
        if u is not None:
            name = (u.get_full_name() or u.username or phone).strip()
            email = (u.email or '').strip()
            has_account = True
        else:
            name = phone
            email = ''
            has_account = False
        out.append(
            {'id': phone, 'name': name, 'phone': phone, 'email': email, 'hasAccount': has_account}
        )
    return out
