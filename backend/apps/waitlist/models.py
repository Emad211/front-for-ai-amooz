"""Waitlist / access-request models.

Teachers and organizations no longer self-register instantly. Instead they
submit an ``AccessRequest`` (a lead). A platform admin reviews it, contacts them
out of band, then approves — approval issues a one-time registration token (and,
for organizations, provisions the Organization + admin code). Only with that
token can the applicant create a real account.

NO account exists until approval (the chosen model), so this table is the sole
record of a pending teacher/org until they are let in.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class AccessRequest(models.Model):
    class Kind(models.TextChoices):
        TEACHER = 'teacher', _('معلم')
        ORGANIZATION = 'organization', _('سازمان')

    class Status(models.TextChoices):
        PENDING = 'pending', _('در انتظار بررسی')
        CONTACTED = 'contacted', _('تماس گرفته شد')
        APPROVED = 'approved', _('تأیید شده')
        REJECTED = 'rejected', _('رد شده')

    kind = models.CharField(max_length=16, choices=Kind.choices, db_index=True)

    # ── Contact (both kinds) ────────────────────────────────────────────────
    full_name = models.CharField(max_length=150, verbose_name=_('نام و نام خانوادگی'))
    phone = models.CharField(max_length=15, db_index=True, verbose_name=_('شماره تماس'))
    email = models.EmailField(blank=True, verbose_name=_('ایمیل'))

    # ── Teacher-specific ────────────────────────────────────────────────────
    expertise = models.CharField(
        max_length=255, blank=True, verbose_name=_('حوزه تدریس / تخصص'),
    )

    # ── Organization-specific ───────────────────────────────────────────────
    org_name = models.CharField(max_length=255, blank=True, verbose_name=_('نام سازمان'))
    city = models.CharField(max_length=120, blank=True, verbose_name=_('شهر'))
    expected_students = models.PositiveIntegerField(
        null=True, blank=True, verbose_name=_('تعداد تقریبی دانش‌آموز'),
    )
    website = models.URLField(blank=True, verbose_name=_('وب‌سایت'))

    # Free-text message from the applicant.
    note = models.TextField(blank=True, verbose_name=_('توضیحات متقاضی'))

    # ── Review state ────────────────────────────────────────────────────────
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reviewed_access_requests',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    admin_note = models.TextField(blank=True, verbose_name=_('یادداشت داخلی'))
    reject_reason = models.CharField(max_length=255, blank=True)

    # ── Outcome links (populated on approval) ───────────────────────────────
    created_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+',
    )
    created_organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+',
    )

    # ── One-time registration token (issued on approval) ────────────────────
    registration_token = models.CharField(max_length=64, blank=True, db_index=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)
    token_consumed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('درخواست دسترسی')
        verbose_name_plural = _('درخواست‌های دسترسی')
        indexes = [
            models.Index(fields=['kind', 'status']),
        ]

    def __str__(self) -> str:
        who = self.org_name or self.full_name
        return f'{self.get_kind_display()} · {who} ({self.get_status_display()})'

    @property
    def is_pending(self) -> bool:
        return self.status == self.Status.PENDING
