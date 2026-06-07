"""Helpers for teacher-scoped messaging.

A teacher's "students" are the distinct phone numbers invited to any of that
teacher's class/exam sessions (excluding the teacher's own phone). These helpers
both power the recipient picker and enforce that a teacher can only message
their own students.
"""
from __future__ import annotations

from apps.accounts.models import User
from apps.classes.models import ClassInvitation


def teacher_student_phones(*, teacher) -> set[str]:
    """Set of distinct student phone numbers across the teacher's sessions."""
    teacher_phone = (getattr(teacher, 'phone', '') or '').strip()
    phones = set()
    for p in (
        ClassInvitation.objects.filter(session__teacher=teacher)
        .values_list('phone', flat=True)
        .distinct()
    ):
        norm = (p or '').strip()
        if norm and norm != teacher_phone:
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
