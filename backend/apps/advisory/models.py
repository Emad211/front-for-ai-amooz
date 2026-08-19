"""Advisory data model.

Step 2 of docs/features/advisor-mvp.md adds exactly one table: the ``Subject``
catalog. Everything the advisor plans and the student logs will hang off a
subject, so this table is the first thing that has to be right.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from .services.text import normalize_subject_name


class Subject(models.Model):
    """A study subject an advisor can plan and a student can log time against.

    Two scopes share one table:

    * ``organization = NULL`` — a **global** subject, visible to every advisor.
      This is the catalog a platform admin curates (ریاضی، فیزیک، …).
    * ``organization = <org>`` — an **organization-private** subject, visible
      only to advisors of that organization.

    A subject is never deleted (``PROTECT`` from ``StudentSubject`` in step 4,
    plus ``is_active=False`` here): a plan written last month must keep making
    sense next month. Deactivating hides it from new pickers and leaves history
    intact.
    """

    name = models.CharField(
        max_length=128,
        verbose_name=_('نام درس'),
        help_text=_('نامی که مشاور و دانش‌آموز می‌بینند (مثلا ریاضی ۱)'),
    )
    # Derived from ``name`` — see services/text.normalize_subject_name. Uniqueness
    # lives here, not on ``name``, because uniqueness on hand-typed Persian text
    # does not stop «ریاضي ۱» / «ریاضی 1» / «ریاضی  ۱» from all coexisting as
    # separate rows, which would fracture one student's subject history.
    normalized_name = models.CharField(
        max_length=128,
        editable=False,
        db_index=True,
        verbose_name=_('کلید یکتاسازی'),
    )
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='advisory_subjects',
        verbose_name=_('سازمان'),
        help_text=_('خالی بگذارید تا این درس برای همه‌ی مشاوران سراسری باشد.'),
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name=_('فعال'),
        help_text=_('غیرفعال‌کردن، درس را از انتخاب‌های جدید حذف می‌کند ولی تاریخ را نگه می‌دارد.'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        verbose_name=_('ایجادکننده'),
    )

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['normalized_name', 'organization'],
                name='uniq_advisory_subject_norm_org',
                violation_error_message=_('این درس در همین سازمان از قبل ثبت شده است.'),
            ),
            # PostgreSQL treats every NULL as distinct, so the constraint above
            # does NOT stop two global rows with the same name. This partial one
            # is what actually makes the global catalog unique.
            models.UniqueConstraint(
                fields=['normalized_name'],
                condition=models.Q(organization__isnull=True),
                name='uniq_advisory_subject_norm_global',
                violation_error_message=_('این درس در فهرست سراسری از قبل ثبت شده است.'),
            ),
        ]
        verbose_name = _('درس')
        verbose_name_plural = _('درس‌ها')

    def __str__(self) -> str:
        if self.organization_id:
            return f'{self.name} ({self.organization})'
        return self.name

    @property
    def is_global(self) -> bool:
        return self.organization_id is None

    def clean(self) -> None:
        """Derive the key and reject a duplicate with a message on ``name``.

        The duplicate check is repeated here on purpose. ``normalized_name`` is
        ``editable=False``, so Django's ModelForm validation excludes it, and
        ``validate_constraints(exclude=…)`` then skips *both* constraints above —
        meaning the admin would otherwise hit a raw ``IntegrityError`` (a 500)
        instead of showing a field error. The DB constraints stay as the hard
        guarantee; this is the human-readable path.
        """
        super().clean()
        self.normalized_name = normalize_subject_name(self.name)
        if not self.normalized_name:
            raise ValidationError({'name': _('نام درس نمی‌تواند خالی باشد.')})

        duplicates = Subject.objects.filter(
            normalized_name=self.normalized_name,
            organization=self.organization,
        )
        if self.pk:
            duplicates = duplicates.exclude(pk=self.pk)
        if duplicates.exists():
            raise ValidationError({
                'name': _('درسی با همین نام در این دامنه از قبل وجود دارد.'),
            })

    def save(self, *args, **kwargs):
        self.normalized_name = normalize_subject_name(self.name)
        # A caller doing save(update_fields=['name']) would otherwise persist a
        # new display name against the old key and silently break uniqueness.
        update_fields = kwargs.get('update_fields')
        if update_fields is not None:
            update_fields = set(update_fields)
            if 'name' in update_fields:
                update_fields.add('normalized_name')
                kwargs['update_fields'] = update_fields
        return super().save(*args, **kwargs)
