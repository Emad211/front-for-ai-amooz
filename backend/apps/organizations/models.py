"""Organization models for multi-tenant school/institute support."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _


# ---------------------------------------------------------------------------
# Organization
# ---------------------------------------------------------------------------

class Organization(models.Model):
    """A school or educational institute (e.g. دبیرستان البرز)."""

    class SubscriptionStatus(models.TextChoices):
        ACTIVE = 'active', _('فعال')
        EXPIRED = 'expired', _('منقضی شده')
        SUSPENDED = 'suspended', _('تعلیق شده')

    name = models.CharField(
        max_length=255,
        verbose_name=_('عنوان سازمان'),
        help_text=_('نام مدرسه یا موسسه'),
    )
    slug = models.SlugField(
        max_length=128,
        unique=True,
        allow_unicode=False,
        verbose_name=_('شناسه یکتا'),
        help_text=_('نام انگلیسی برای آدرس اینترنتی (مثلا alborz-high)'),
    )
    logo = models.ImageField(
        upload_to='organizations/logos/',
        blank=True,
        null=True,
        verbose_name=_('لوگوی سازمان'),
    )
    student_capacity = models.PositiveIntegerField(
        default=100,
        verbose_name=_('ظرفیت دانش‌آموز'),
        help_text=_('سقف تعداد دانش‌آموزی که سازمان پولش را داده'),
    )
    subscription_status = models.CharField(
        max_length=16,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.ACTIVE,
        db_index=True,
        verbose_name=_('وضعیت اشتراک'),
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='owned_organizations',
        verbose_name=_('مالک اصلی'),
        help_text=_('کاربری که مدیر کل این سازمان است'),
    )

    # Optional metadata
    description = models.TextField(blank=True, verbose_name=_('توضیحات'))
    phone = models.CharField(max_length=20, blank=True, verbose_name=_('تلفن'))
    address = models.TextField(blank=True, verbose_name=_('آدرس'))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('سازمان')
        verbose_name_plural = _('سازمان‌ها')

    def __str__(self) -> str:
        return self.name

    # ---------- helpers ----------

    @property
    def current_student_count(self) -> int:
        return self.memberships.filter(
            org_role=OrganizationMembership.OrgRole.STUDENT,
            status=OrganizationMembership.MemberStatus.ACTIVE,
        ).count()

    @property
    def is_at_capacity(self) -> bool:
        return self.current_student_count >= self.student_capacity


# ---------------------------------------------------------------------------
# OrganizationMembership
# ---------------------------------------------------------------------------

class OrganizationMembership(models.Model):
    """Links a user to an organization with a specific role."""

    class OrgRole(models.TextChoices):
        ADMIN = 'admin', _('مدیر')
        DEPUTY = 'deputy', _('معاون')
        TEACHER = 'teacher', _('معلم')
        STUDENT = 'student', _('دانش‌آموز')

    class MemberStatus(models.TextChoices):
        ACTIVE = 'active', _('فعال')
        SUSPENDED = 'suspended', _('تعلیق شده')

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='org_memberships',
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='memberships',
    )
    org_role = models.CharField(
        max_length=16,
        choices=OrgRole.choices,
        default=OrgRole.STUDENT,
        verbose_name=_('نقش سازمانی'),
    )
    internal_id = models.CharField(
        max_length=64,
        blank=True,
        verbose_name=_('شناسه داخلی'),
        help_text=_('شماره دانش‌آموزی یا کد پرسنلی معلم'),
    )
    status = models.CharField(
        max_length=16,
        choices=MemberStatus.choices,
        default=MemberStatus.ACTIVE,
        db_index=True,
    )

    joined_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-joined_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'organization'],
                name='uniq_membership_user_org',
            ),
        ]
        verbose_name = _('عضویت سازمانی')
        verbose_name_plural = _('عضویت‌های سازمانی')

    def __str__(self) -> str:
        return f'{self.user} → {self.organization} ({self.get_org_role_display()})'


# ---------------------------------------------------------------------------
# InvitationCode
# ---------------------------------------------------------------------------

def _generate_invite_code() -> str:
    """Generate a human-readable invite code like ALBORZ-TEACH-A3K9."""
    suffix = get_random_string(length=6, allowed_chars='ABCDEFGHJKLMNPQRSTUVWXYZ23456789')
    return suffix


class InvitationCode(models.Model):
    """Reusable invitation code to join an organization."""

    class TargetRole(models.TextChoices):
        ADMIN = 'admin', _('مدیر')
        DEPUTY = 'deputy', _('معاون')
        TEACHER = 'teacher', _('معلم')
        STUDENT = 'student', _('دانش‌آموز')

    code = models.CharField(
        max_length=64,
        unique=True,
        default=_generate_invite_code,
        verbose_name=_('کد دعوت'),
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='invitation_codes',
    )
    target_role = models.CharField(
        max_length=16,
        choices=TargetRole.choices,
        default=TargetRole.STUDENT,
        verbose_name=_('نقش هدف'),
    )
    label = models.CharField(
        max_length=128,
        blank=True,
        verbose_name=_('برچسب'),
        help_text=_('نام توصیفی مثلا "دهم-ریاضی" یا "معلمان فیزیک"'),
    )
    max_uses = models.PositiveIntegerField(
        default=30,
        verbose_name=_('ظرفیت استفاده'),
    )
    use_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_('دفعات استفاده شده'),
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('تاریخ انقضا'),
    )
    is_active = models.BooleanField(default=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_invitation_codes',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('کد دعوت')
        verbose_name_plural = _('کدهای دعوت')

    def __str__(self) -> str:
        return f'{self.code} ({self.organization.name})'

    @property
    def is_valid(self) -> bool:
        """Check if code can still be used."""
        if not self.is_active:
            return False
        if self.use_count >= self.max_uses:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        if self.organization.subscription_status != Organization.SubscriptionStatus.ACTIVE:
            return False
        return True

    @property
    def remaining_uses(self) -> int:
        return max(0, self.max_uses - self.use_count)
