"""Advisory data model.

Step 2 of docs/features/advisor-mvp.md added the ``Subject`` catalog. Step 3 adds
``AdvisoryEngagement`` — the row that ties one advisor to one student and becomes
the **tenancy carrier** for every table after it: a plan, a log and a subject
selection all hang off an engagement, never off a ``User``. That is what makes
every later authorization query a join with an owner in it rather than a
"current user" comparison that is easy to forget.

Step 4 added ``StudentSubject`` (the advisor's per-student picks). Both are
tenancy-bearing and reachable only through ``services/scope.py`` plus their
write doors — see ``test_import_boundaries``.
"""

import datetime

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .services.text import normalize_subject_name

# How long an unanswered invite stays claimable (B6). Long enough that a student
# who only opens the app on weekends still finds it; short enough that a roster
# of forgotten invites does not accumulate into a permanent claim on someone.
INVITE_TTL_DAYS = 14

# After a student rejects an advisor, that exact pair is blocked for this long
# (B6). ``REJECTED`` is terminal: the advisor may not simply re-invite the next
# minute, which is what turns "no" into a real answer instead of a rate limit.
REJECT_BLOCK_DAYS = 30

# ── national-curriculum identity axes ────────────────────────────────────────
# A subject's identity is (normalized_name, grade, major, organization): the same
# name at two grades — or in two majors — is two different subjects. This REVERSES
# the S4 meaning of ``grade``, which used to be a non-identity "convenience filter"
# where NULL meant "all levels". It no longer does; the three cases a derivation
# reads (services/scope.curriculum_subjects) are:
#
#   * grade = NULL            → INVISIBLE to every student. A gradeless row derives
#                               for nobody — it is dead/legacy, NOT "all grades".
#   * grade set, major = NULL → SHARED by every major of that grade: the general
#                               subjects (دینی/فارسی/عربی/زبان) and any grade whose
#                               curriculum is not split by major.
#   * grade set, major set    → specific to one major.
#
# Both lists mirror ``accounts.StudentProfile`` **by value**, so a student's own
# (grade, major) selects their curriculum directly. They are duplicated here rather
# than imported, to keep advisory free of a cross-app dependency on accounts.
SUBJECT_GRADE_CHOICES = [
    ('10', _('دهم')),
    ('11', _('یازدهم')),
    ('12', _('دوازدهم')),
]

# Mirror of ``accounts.StudentProfile.MAJOR_CHOICES`` by value. NULL is meaningful
# here, not "unset": a NULL-major subject is the general one shared across every
# major of its grade (see the matrix above), so it is a first-class identity value.
SUBJECT_MAJOR_CHOICES = [
    ('math', _('ریاضی فیزیک')),
    ('science', _('علوم تجربی')),
    ('humanities', _('علوم انسانی')),
]


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
    # Part of identity (see SUBJECT_GRADE_CHOICES and the constraint below), and a
    # gate for derivation: a NULL grade makes the subject derive for nobody. It is
    # NOT touched by clean()/save() because it does not feed ``normalized_name`` —
    # but it *is* one of the four columns the identity constraint keys on.
    grade = models.CharField(
        max_length=2,
        choices=SUBJECT_GRADE_CHOICES,
        blank=True,
        null=True,
        db_index=True,
        verbose_name=_('پایه‌ی تحصیلی'),
        help_text=_('بخشی از هویتِ درس؛ خالی یعنی این درس برای هیچ دانش‌آموزی مشتق نمی‌شود.'),
    )
    # The other identity axis. NULL means "general" — shared across every major of
    # this grade — not "unset" (see the matrix on SUBJECT_MAJOR_CHOICES). Mirrors
    # ``accounts.StudentProfile.major`` by value so a student's own major derives it.
    major = models.CharField(
        max_length=20,
        choices=SUBJECT_MAJOR_CHOICES,
        blank=True,
        null=True,
        db_index=True,
        verbose_name=_('رشته‌ی تحصیلی'),
        help_text=_('بخشی از هویتِ درس؛ خالی یعنی درسِ عمومیِ مشترک بینِ همه‌ی رشته‌های این پایه.'),
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
            # Identity is the whole four-tuple: the same name at two grades, in two
            # majors, or in a national row vs an org-private one are all distinct
            # subjects. ``nulls_distinct=False`` (PG15+ ``UNIQUE NULLS NOT DISTINCT``)
            # is load-bearing — without it PostgreSQL treats each NULL as distinct and
            # two national rows (organization/major both NULL) with the same name slip
            # through, exactly the fracturing ``normalized_name`` exists to prevent.
            models.UniqueConstraint(
                fields=['normalized_name', 'grade', 'major', 'organization'],
                nulls_distinct=False,
                name='uniq_advisory_subject_identity',
                violation_error_message=_('این درس با همین پایه و رشته از قبل ثبت شده است.'),
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
        ``validate_constraints(exclude=…)`` then skips the identity constraint above
        — meaning the admin would otherwise hit a raw ``IntegrityError`` (a 500)
        instead of showing a field error. The DB constraint stays as the hard
        guarantee; this is the human-readable path, and it must key on the same
        four columns (``grade``/``major`` included, ``field=None`` → ``IS NULL``)
        or it would reject a legitimately-distinct grade/major variant.
        """
        super().clean()
        self.normalized_name = normalize_subject_name(self.name)
        if not self.normalized_name:
            raise ValidationError({'name': _('نام درس نمی‌تواند خالی باشد.')})

        duplicates = Subject.objects.filter(
            normalized_name=self.normalized_name,
            grade=self.grade,
            major=self.major,
            organization=self.organization,
        )
        if self.pk:
            duplicates = duplicates.exclude(pk=self.pk)
        if duplicates.exists():
            raise ValidationError({
                'name': _('درسی با همین نام، پایه و رشته در این دامنه از قبل وجود دارد.'),
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


class AdvisoryEngagement(models.Model):
    """One advisor working with one student — the tenancy carrier of the feature.

    Every advisory table added after this one points at an engagement rather than
    at a ``User``, so "may this advisor read this row?" is always answered by the
    same single join (see ``services/scope.py``). Nothing else in the app is
    allowed to invent its own ownership rule.

    Lifecycle::

        PENDING ──accept──▶ ACTIVE ──end──▶ ENDED
           └────reject────▶ REJECTED   (terminal; the pair is blocked 30 days)

    ``PENDING`` is created by the advisor, but only ever **claimed** by the
    student: an invite is an offer, not an assignment. The advisor gets no data
    at all until the student presses «قبول».
    """

    class Mode(models.TextChoices):
        FREELANCE = 'freelance', _('فریلنسر')
        ORG = 'org', _('سازمانی')

    class Status(models.TextChoices):
        PENDING = 'PENDING', _('در انتظار پذیرش')
        ACTIVE = 'ACTIVE', _('فعال')
        REJECTED = 'REJECTED', _('رد شده')
        ENDED = 'ENDED', _('پایان‌یافته')

    advisor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='advisory_engagements',
        limit_choices_to={'role': 'ADVISOR'},
        verbose_name=_('مشاور'),
    )
    # CASCADE, unlike the advisor's PROTECT: a student who leaves the platform
    # takes their study history with them (D3 — the log belongs to the student),
    # whereas an advisor with live students must not be deletable at all.
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='advisory_engagements_as_student',
        verbose_name=_('دانش‌آموز'),
    )
    # The canonical phone the advisor addressed the invite to. Kept so that
    # accepting can re-verify it against the claimant's current phone (B6): if
    # the number changed hands between invite and accept, the invite is dead
    # rather than a handover of one student's data to a different human.
    invited_phone = models.CharField(
        max_length=15,
        blank=True,
        default='',
        verbose_name=_('شماره‌ی دعوت‌شده'),
    )
    mode = models.CharField(
        max_length=10,
        choices=Mode.choices,
        default=Mode.FREELANCE,
        verbose_name=_('نوع همکاری'),
    )
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='advisory_engagements',
        verbose_name=_('سازمان'),
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name=_('وضعیت'),
    )
    invited_at = models.DateTimeField(auto_now_add=True, verbose_name=_('زمان دعوت'))
    invite_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('انقضای دعوت'),
    )
    # A date, not a datetime: plans and logs are day-grained, and «از امروز»
    # must not depend on which side of midnight UTC the accept landed.
    started_on = models.DateField(null=True, blank=True, verbose_name=_('شروع همکاری'))
    # Terminal timestamp for BOTH ``REJECTED`` and ``ENDED`` — one field, because
    # the 30-day re-invite block only ever needs "when did this stop".
    ended_at = models.DateTimeField(null=True, blank=True, verbose_name=_('زمان پایان'))
    terms_accepted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('زمان پذیرش شرایط'),
    )

    class Meta:
        ordering = ['-invited_at']
        constraints = [
            # ``mode`` and ``organization`` must agree. Without this, an "org"
            # engagement with a NULL organization would read as freelance to
            # every scope query and quietly escape the organization gate.
            models.CheckConstraint(
                condition=(
                    models.Q(mode='freelance', organization__isnull=True)
                    | models.Q(mode='org', organization__isnull=False)
                ),
                name='ck_advisory_engagement_mode_org',
                violation_error_message=_('همکاری سازمانی باید سازمان داشته باشد و فریلنسری نباید.'),
            ),
            # One active advisor per student. Partial, so the rejected and ended
            # history of the same student stays queryable.
            models.UniqueConstraint(
                fields=['student'],
                condition=models.Q(status='ACTIVE'),
                name='uniq_active_advisory_per_student',
                violation_error_message=_('این دانش‌آموز از قبل مشاور فعال دارد.'),
            ),
            # Anti-spam: one open invite per (advisor, student) pair.
            models.UniqueConstraint(
                fields=['advisor', 'student'],
                condition=models.Q(status='PENDING'),
                name='uniq_pending_advisory_invite',
                violation_error_message=_('دعوت‌نامه‌ی باز برای این دانش‌آموز از قبل وجود دارد.'),
            ),
        ]
        indexes = [
            models.Index(fields=['advisor', 'status'], name='idx_adv_eng_advisor_status'),
            models.Index(fields=['student', 'status'], name='idx_adv_eng_student_status'),
            models.Index(
                fields=['status', 'invite_expires_at'],
                name='idx_adv_eng_status_expires',
            ),
        ]
        verbose_name = _('همکاری مشاوره')
        verbose_name_plural = _('همکاری‌های مشاوره')

    def __str__(self) -> str:
        return f'{self.advisor} → {self.student} ({self.get_status_display()})'

    @property
    def is_expired(self) -> bool:
        """A ``PENDING`` invite past its TTL. Never true for a settled row."""
        if self.status != self.Status.PENDING or self.invite_expires_at is None:
            return False
        return self.invite_expires_at <= timezone.now()

    @classmethod
    def default_invite_expiry(cls) -> datetime.datetime:
        return timezone.now() + datetime.timedelta(days=INVITE_TTL_DAYS)

    def clean(self) -> None:
        """Mirror the mode/organization check with a field-level message.

        The DB constraint is the guarantee; this is what the Django admin and any
        serializer calling ``full_clean()`` can actually show a human.
        """
        super().clean()
        if self.mode == self.Mode.ORG and self.organization_id is None:
            raise ValidationError({
                'organization': _('برای همکاری سازمانی، سازمان الزامی است.'),
            })
        if self.mode == self.Mode.FREELANCE and self.organization_id is not None:
            raise ValidationError({
                'organization': _('همکاری فریلنسری نمی‌تواند سازمان داشته باشد.'),
            })


class StudentSubject(models.Model):
    """A subject an advisor has selected **for one specific student** (S4).

    This is the first table that hangs off an ``AdvisoryEngagement`` rather than a
    ``User`` — the tenancy-carrier pattern the whole feature is built on. "May this
    advisor edit this selection?" is answered by the engagement's owner, through
    ``services/scope.py`` (read) and ``services/student_subjects.py`` (write);
    nothing here invents its own ownership rule. It is therefore **tenancy-bearing**
    and must not be imported outside those doors (``test_import_boundaries``).

    A selection is never row-deleted. Removing a subject flips ``is_active`` to
    ``False`` and re-adding it flips it back — the same "deactivate, keep history"
    philosophy ``Subject`` itself follows, and what lets a later plan (step 8) point
    at a stable set of ids without the row underneath it ever vanishing.
    """

    engagement = models.ForeignKey(
        AdvisoryEngagement,
        on_delete=models.CASCADE,
        related_name='subject_selections',
        verbose_name=_('همکاری'),
    )
    # PROTECT, honouring the promise in Subject's own docstring: a subject a student
    # has ever studied must not be deletable out from under a selection or a plan.
    subject = models.ForeignKey(
        Subject,
        on_delete=models.PROTECT,
        related_name='+',
        verbose_name=_('درس'),
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name=_('فعال'),
        help_text=_('غیرفعال یعنی از انتخاب فعلی حذف شده؛ تاریخ نگه داشته می‌شود.'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['subject__name']
        constraints = [
            # One row per (engagement, subject): re-adding a removed subject
            # reactivates the existing row instead of inserting a duplicate. This
            # is what makes the set-replace in student_subjects.set_engagement_subjects
            # a get_or_create + toggle rather than a delete + re-insert.
            models.UniqueConstraint(
                fields=['engagement', 'subject'],
                name='uniq_advisory_student_subject',
                violation_error_message=_('این درس برای این دانش‌آموز از قبل ثبت شده است.'),
            ),
        ]
        indexes = [
            models.Index(
                fields=['engagement', 'is_active'],
                name='idx_adv_studsub_eng_active',
            ),
        ]
        verbose_name = _('درسِ دانش‌آموز')
        verbose_name_plural = _('درس‌های دانش‌آموز')

    def __str__(self) -> str:
        state = '' if self.is_active else ' (غیرفعال)'
        return f'{self.subject} ← #{self.engagement_id}{state}'
