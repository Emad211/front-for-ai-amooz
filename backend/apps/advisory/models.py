"""Advisory data model.

Step 2 of docs/features/advisor-mvp.md added the ``Subject`` catalog. Step 3 adds
``AdvisoryEngagement`` — the row that ties one advisor to one student and becomes
the **tenancy carrier** for every table after it: a plan, a log and a subject
selection all hang off an engagement, never off a ``User``. That is what makes
every later authorization query a join with an owner in it rather than a
"current user" comparison that is easy to forget.

Step 4 added ``StudentSubject`` (the advisor's per-student picks) and step 5 adds
``DailyLog`` / ``DailyLogItem`` (the student's own minutes, reported against those
picks). All three are tenancy-bearing and reachable only through
``services/scope.py`` plus their write doors — see ``test_import_boundaries``.
"""

import datetime

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .services.calendar import ensure_saturday
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
    ('01', _('پایه اول')),
    ('02', _('پایه دوم')),
    ('03', _('پایه سوم')),
    ('04', _('پایه چهارم')),
    ('05', _('پایه پنجم')),
    ('06', _('پایه ششم')),
    ('07', _('هفتم')),
    ('08', _('هشتم')),
    ('09', _('نهم')),
    ('10', _('دهم')),
    ('11', _('یازدهم')),
    ('12', _('دوازدهم')),
]

# Mirror of ``accounts.StudentProfile.MAJOR_CHOICES`` by value. NULL is meaningful
# here, not "unset": a NULL-major subject is the general one shared across every
# major of its grade (see the matrix above), so it is a first-class identity value.
# ``theology``/``technical`` arrived with the national-curriculum ingest (Step 9);
# ``technical`` rows are kept out of catalog v1 by the conversion rules, but the
# code stays valid so org-curated subjects may still use it.
SUBJECT_MAJOR_CHOICES = [
    ('math', _('ریاضی فیزیک')),
    ('science', _('علوم تجربی')),
    ('humanities', _('علوم انسانی')),
    ('theology', _('علوم و معارف اسلامی')),
    ('technical', _('فنی و حرفه‌ای و کاردانش')),
]

# Restart plan, step 3 (wave-2 phase 1): which physical source each selected
# subject is studied from (PDF ص۵). The raw codes are the wire contract; the
# Persian labels are rendered client-side from the same map the picker ships,
# so both live here next to the column they describe.
SUBJECT_SOURCE_CHOICES = [
    ('TEXTBOOK', _('کتاب درسی')),
    ('TEACHER_BOOKLET', _('جزوه معلم')),
    ('VIDEO', _('فیلم')),
    ('KONKUR_BOOKLET', _('جزوه/دفترنامۀ کنکور')),
    ('OTHER', _('سایر')),
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
    # Risman step 1: the advisor's private grouping of their roster. SET_NULL
    # per ق۷ — deleting a folder must not delete the engagements inside it;
    # they simply fall back to «بدون پوشه». The FK hangs off the engagement
    # (the tenancy carrier), never off a ``User``, so a folder move is just
    # another engagement-scoped write resolved through ``services/scope.py``.
    folder = models.ForeignKey(
        'AdvisoryStudentFolder',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='engagements',
        verbose_name=_('پوشه'),
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
    # Restart step 3: which source the student studies this subject from.
    # Nullable, not defaulted: «مشاور هنوز انتخاب نکرده» must stay distinct from
    # any of the five codes, and a deactivated row keeps its last source so the
    # history a plan pointed at never loses its answer.
    source = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        choices=SUBJECT_SOURCE_CHOICES,
        verbose_name=_('منبع مطالعه'),
        help_text=_('منبعی که دانش‌آموز این درس را با آن می‌خواند؛ خالی یعنی ثبت نشده.'),
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


# ── S5: the daily study log ──────────────────────────────────────────────────
# One item's ceiling. 960 = 16h, the same bound the sibling
# ``WeeklyPlanItem.planned_minutes`` carries in the spec (§2), because a plan and
# the log reporting against it must share a scale or the S8 commitment ratio
# (actual ÷ planned) silently compares two different units. It is deliberately
# generous: the job is to stop a fat-fingered «4500» from poisoning that metric,
# not to argue with a student about whether they really studied twelve hours.
MAX_LOG_MINUTES_PER_ITEM = 960

# ...and one *day's* ceiling, across every subject. A day holds 1440 minutes, and
# with up to ``MAX_SUBJECTS_PER_STUDENT`` (60) subjects the per-item cap alone would
# still permit 57,600 — a commitment ratio of 4000%. Enforced in
# ``services/daily_logs`` and not as a ``CheckConstraint``, because a DB check
# cannot sum sibling rows; the per-item check below is the part the DB can hold.
MAX_LOG_MINUTES_PER_DAY = 1440

# Note length. The column stays a ``TextField`` — a note is prose, not a label, and
# a student writing «امروز فیزیک سخت بود چون...» must not hit a column error — so the
# bound is enforced by the serializer. This is the one place the number is defined.
MAX_LOG_NOTE_CHARS = 1000

# Mood is a 1..5 scale, not an enum: the frontend renders five faces, the S6 advisor
# feed averages it, and neither wants named members. Bounds live here so the model
# constraint, the serializer and the tests all read the same two numbers.
MOOD_MIN = 1
MOOD_MAX = 5


class DailyLog(models.Model):
    """One day of a student's self-reported study, hanging off the engagement (S5).

    **The student writes this; the advisor only ever reads it.** That is D3, and it
    is the reason the write door (``services/daily_logs``) takes a *student*, not an
    actor: there is no code path by which an advisor edits a log, so there is none to
    get the permission check wrong in. An advisor who disagrees with a number talks
    to their student.

    Why it hangs off ``AdvisoryEngagement`` and not off ``User``, when the data is
    the student's own: the engagement is the tenancy carrier, and it carries the
    *time window* too. ``started_on`` is the day the student accepted, so scoping
    logs to the engagement makes C3 (no retroactive visibility) a property of the
    schema rather than a filter someone must remember — an advisor cannot see the
    month before they were hired because those rows belong to no engagement of
    theirs. The cost is that a student with no advisor has nowhere to log, which is
    correct for the MVP: this is an advisory feature, not a general study tracker.

    One row per (engagement, day). A save replaces the day wholesale (set-replace on
    the items) and never deletes the row — an existing log with zero items means «I
    reported, and it was nothing», which is a different fact from no log at all, and
    the S8 metric needs to tell them apart.

    Retention is 730 days (D2). No sweeper ships in S5 — the MVP has no Celery — so
    that is a documented future, not a live behaviour.
    """

    engagement = models.ForeignKey(
        AdvisoryEngagement,
        on_delete=models.CASCADE,
        related_name='daily_logs',
        verbose_name=_('همکاری'),
    )
    # A date, not a datetime, for the reason ``started_on`` is one: a study day is a
    # day. Which side of midnight UTC the request landed on must not move a log.
    log_date = models.DateField(
        verbose_name=_('تاریخ'),
        help_text=_('روزی که این گزارش برای آن است (میلادی؛ نمایش شمسی در فرانت‌اند).'),
    )
    mood = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name=_('حال و حوصله'),
        help_text=_('عددی از ۱ تا ۵. خالی یعنی دانش‌آموز ثبت نکرده — که با «۱» یکی نیست.'),
    )
    note = models.TextField(
        blank=True,
        default='',
        verbose_name=_('یادداشت'),
        help_text=_('یادداشت آزاد دانش‌آموز برای آن روز.'),
    )
    # ── Restart plan, step 1 (wave-1 unit B): PDF-derived day enrichment ─────
    # Four additive columns from the paper checklist (PDF ص۸-۹). «رضایت»
    # deliberately gets NO new column — the existing ``mood`` above IS the
    # satisfaction metric; these four only add what mood cannot carry.
    day_goal = models.CharField(
        max_length=200,
        blank=True,
        default='',
        verbose_name=_('هدف روز'),
        help_text=_('هدف‌گذاری دانش‌آموز برای امروز.'),
    )
    motivation_note = models.CharField(
        max_length=200,
        blank=True,
        default='',
        verbose_name=_('جمله انگیزشی'),
        help_text=_('شعار یا جمله انگیزشی که دانش‌آموز برای امروز نوشته است.'),
    )
    tests_taken = models.PositiveIntegerField(
        default=0,
        verbose_name=_('تعداد تست'),
        help_text=_('تعداد تست‌هایی که امروز زده شده است.'),
    )
    # Nullable like ``mood``: «ثبت نکردم» must stay distinguishable from «۰٪».
    test_percent = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name=_('درصد آزمون'),
        help_text=_('درصد آزمون امروز؛ خالی یعنی ثبت نشده — که با «۰» یکی نیست.'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Newest day first: every reader of a log list — the student's own history,
        # the S6 advisor feed — wants the most recent day at the top.
        ordering = ['-log_date']
        constraints = [
            models.UniqueConstraint(
                fields=['engagement', 'log_date'],
                name='uniq_advisory_daily_log',
                violation_error_message=_('برای این روز از قبل گزارشی ثبت شده است.'),
            ),
            # NULL passes: «not reported» is a legal state, and a NULL-rejecting
            # check here would force the client to invent a sentinel mood.
            models.CheckConstraint(
                condition=(
                    models.Q(mood__isnull=True)
                    | models.Q(mood__gte=MOOD_MIN, mood__lte=MOOD_MAX)
                ),
                name='ck_advisory_log_mood_range',
                violation_error_message=_('حال و حوصله باید عددی بین ۱ تا ۵ باشد.'),
            ),
        ]
        indexes = [
            # (engagement, newest-first) — the shape of every read: "this student's
            # last N days". Matches ``ordering`` so the sort is index-served.
            models.Index(
                fields=['engagement', '-log_date'],
                name='idx_adv_log_eng_date',
            ),
        ]
        verbose_name = _('گزارش روزانه')
        verbose_name_plural = _('گزارش‌های روزانه')

    def __str__(self) -> str:
        return f'{self.log_date} ← #{self.engagement_id}'


LOG_ACTIVITY_CHOICES = [
    ('LESSON', _('درسنامه')),
    ('EDU_TEST', _('تست آموزشی')),
    ('TIMED_TEST', _('تست زمان‌دار')),
    ('REVIEW', _('مرور')),
    ('SUMMARY', _('خلاصه‌نویسی')),
]


class DailyLogItem(models.Model):
    """Minutes studied on one subject, on one day.

    The FK is to ``StudentSubject``, **not to ``Subject``** — the join key decision
    locked in S4 so that the S8 commitment metric (actual ÷ planned, grouped by the
    subjects the advisor actually focused) needs no migration to compute. It also
    means a log line can only ever name a subject that *was* on this student's list,
    which is a data-integrity property no validation can be forgotten out of.

    ``PROTECT`` on that FK, matching ``StudentSubject.subject``: a selection row a
    student has logged hours against must not be deletable out from under the
    history. It never is in practice — S4 removes a subject by flipping ``is_active``,
    never by deleting — and PROTECT is what keeps that true if someone ever reaches
    for ``.delete()``.

    A consequence worth stating, because it looks like a bug from either end: an item
    may point at a **deactivated** ``StudentSubject``. The student logged 40 minutes
    of شیمی on Monday; on Tuesday the advisor dropped شیمی from the list. Monday's 40
    minutes must not vanish. So the *write* path accepts only currently-active
    selections (``services/daily_logs``) while the *read* path filters by neither —
    it returns whatever was recorded. Do not "tidy up" the read with
    ``student_subject__is_active=True``; that silently rewrites history.
    """

    log = models.ForeignKey(
        DailyLog,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name=_('گزارش روزانه'),
    )
    student_subject = models.ForeignKey(
        StudentSubject,
        on_delete=models.PROTECT,
        related_name='log_items',
        verbose_name=_('درسِ دانش‌آموز'),
    )
    actual_minutes = models.PositiveIntegerField(
        verbose_name=_('دقیقه‌ی مطالعه'),
        help_text=_('دقیقه‌ی واقعیِ مطالعه‌ی این درس در آن روز.'),
    )
    # Research wave (2026-08-31): what those minutes actually were — the
    # activity taxonomy Iranian planning forms separate (درسنامه/تست آموزشی/
    # تست زمان‌دار/مرور/خلاصه‌نویسی). Blank = plain minutes, the pre-field row.
    activity_type = models.CharField(
        max_length=12,
        blank=True,
        default='',
        choices=LOG_ACTIVITY_CHOICES,
        verbose_name=_('نوع مطالعه'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['student_subject__subject__name']
        constraints = [
            models.UniqueConstraint(
                fields=['log', 'student_subject'],
                name='uniq_advisory_daily_log_item',
                violation_error_message=_('برای این درس در این روز از قبل دقیقه ثبت شده است.'),
            ),
            # Strictly positive: a zero-minute row is not data, it is a subject the
            # student left blank, and the write door drops those instead of storing
            # rows that would then have to be filtered out of every later average.
            models.CheckConstraint(
                condition=models.Q(
                    actual_minutes__gt=0,
                    actual_minutes__lte=MAX_LOG_MINUTES_PER_ITEM,
                ),
                name='ck_advisory_log_item_minutes',
                violation_error_message=_('دقیقه‌ی مطالعه باید بین ۱ تا ۹۶۰ باشد.'),
            ),
        ]
        verbose_name = _('دقیقه‌ی درس')
        verbose_name_plural = _('دقیقه‌های درس')

    def __str__(self) -> str:
        return f'{self.student_subject_id}: {self.actual_minutes}د'


# ── S7 (§14 redesign): the study plan — a variable horizon, not a week ───────
# The longest horizon a plan may span. §14 replaced the Saturday-anchored week
# with a free start date plus a length of 7/14/30 or «custom» up to this ceiling;
# 90 days is also why ``StudyPlanItem.day_offset`` is checked against 0..89.
MAX_PLAN_DURATION_DAYS = 90

# The DB-side bound on one item's day offset. The *real* cap —
# ``day_offset < duration_days`` — cannot be a column check (it compares sibling
# columns of the parent row), so it lives in ``services/study_plans``; this check
# only stops a corrupt row from carrying an offset no legal plan could address.
MAX_PLAN_DAY_OFFSET = MAX_PLAN_DURATION_DAYS - 1

# One planned item's ceiling, on the same scale as the log's ``actual_minutes``
# (960 = 16h): the S8 commitment ratio divides actual by planned, so both sides
# must share their unit or the percentage silently compares two different things.
MAX_PLAN_MINUTES_PER_ITEM = MAX_LOG_MINUTES_PER_ITEM

# Restart plan, step 4 (wave-2 phase 2): per-row enrichment bounds. ``test_minutes``
# is a *within-a-study-block* budget, not a second duration column, so it is capped
# well under the row's own 960-minute study ceiling; nullable because «مشاور
# زمانی برای تست نگذاشته» stays distinct from an honest «۰».
MAX_PLAN_TEST_MINUTES = 480

MASTERY_COLOR_CHOICES = [
    ('RED', _('قرمز')),
    ('YELLOW', _('زرد')),
    ('GREEN', _('سبز')),
]

# Research wave (2026-08-31): the roadmap vocabulary of Iranian consultants —
# plan phases (konkurmoshaver/irantahsil roadmaps) and the volume/time strategy
# axis, plus the study-activity taxonomy every planning form separates.
PLAN_PHASE_CHOICES = [
    ('BASE', _('پایه‌سازی')),
    ('TEST', _('تست‌زنی')),
    ('REVIEW', _('جمع‌بندی')),
    ('FINAL', _('هفته‌های آخر')),
]

PLAN_STRATEGY_CHOICES = [
    ('VOLUME', _('حجمی')),
    ('TIME', _('زمانی')),
    ('HYBRID', _('حجمی-زمانی')),
]

# The allowed sub-keys of one day's note block and their ceiling. The shape is
# validated by hand in services/study_plans.save_draft (not JSON schema) per the
# restart plan; these constants are the single definition both sides read.
DAY_NOTE_FIELDS = ('school', 'exams', 'konkurClass', 'preReading')
MAX_DAY_NOTE_CHARS = 120

# The one action ``AdvisoryAccessLog`` records in the MVP: the advisor opening a
# student's study feed (D4 — reads are logged from the moment they exist).
STUDY_FEED_VIEW_ACTION = 'study_feed_view'


class StudyPlan(models.Model):
    """A plan the advisor lays over a **variable horizon** (S7, redesigned in §14).

    Not a week anchored to Saturday anymore: the advisor picks any ``start_date``
    (never before ``started_on`` — C3 for writes) and any length of 1..90 days,
    which is what lets «۷/۱۴/۳۰ روز» be chips on the frontend rather than schema.
    Like every advisory table it hangs off the engagement — the tenancy carrier —
    so "may this advisor edit this plan?" stays the same single join as everywhere
    else, answered by ``services/scope.py``.

    Lifecycle is two states::

        DRAFT ──publish──▶ PUBLISHED ──unpublish──▶ DRAFT   (the §5 rollback lever)

    Exactly **one** DRAFT per engagement (partial unique constraint below): the
    draft is a scratch slot the planner form upserts wholesale, not a document
    history. Several PUBLISHED plans may coexist; that they must not overlap in
    time is a *service* rule (``services/study_plans.publish_draft``), not a
    constraint — exclusion constraints over computed end dates are not worth the
    migration complexity for an MVP where one advisor writes one student's plans.

    There is no automatic repetition in the MVP: when a horizon ends, the advisor
    builds the next plan.
    """

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', _('پیش‌نویس')
        PUBLISHED = 'PUBLISHED', _('منتشرشده')

    engagement = models.ForeignKey(
        AdvisoryEngagement,
        on_delete=models.PROTECT,
        related_name='study_plans',
        verbose_name=_('همکاری'),
    )
    # Free start, but never before the engagement began: a plan starting before
    # ``started_on`` would promise work in days the advisor was not yet party to
    # (C3). Enforced by the write door, not here — the model cannot see whether a
    # caller already resolved ownership, and a constraint would fire as a 500.
    start_date = models.DateField(
        verbose_name=_('تاریخ شروع'),
        help_text=_('آزاد؛ نباید پیش از شروع همکاری باشد (قاعده‌ی C3 برای نوشتن).'),
    )
    duration_days = models.PositiveSmallIntegerField(
        verbose_name=_('طول برنامه (روز)'),
        help_text=_('بین ۱ و ۹۰ روز؛ چیپ‌های ۷/۱۴/۳۰ فقط میان‌برهای همین عددند.'),
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
        verbose_name=_('وضعیت'),
    )
    # Restart step 4: per-day notes (school / exams / konkur class / pre-reading),
    # keyed '0'..'6' as strings. Shape is enforced by the write door, not here —
    # a JSONField cannot express «str ≤ 120 under known keys only».
    day_notes = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('یادداشت روزها'),
        help_text=_('شکل مجاز: {"<0..6>": {"school": str≤120, "exams": …, "konkurClass": …, "preReading": …}}'),
    )
    # Research wave (2026-08-31): the plan's phase and volume/time strategy —
    # the two axes every Iranian consultant's roadmap names (پایه‌سازی → تست‌زنی
    # → جمع‌بندی → هفته‌های آخر; حجمی/زمانی/حجمی-زمانی). Optional: plans
    # written before the field (or without it) stay legal and render bare.
    phase = models.CharField(
        max_length=10,
        blank=True,
        default='',
        choices=PLAN_PHASE_CHOICES,
        verbose_name=_('فاز برنامه'),
    )
    strategy = models.CharField(
        max_length=10,
        blank=True,
        default='',
        choices=PLAN_STRATEGY_CHOICES,
        verbose_name=_('استراتژی برنامه'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['start_date', 'id']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    duration_days__gte=1,
                    duration_days__lte=MAX_PLAN_DURATION_DAYS,
                ),
                name='ck_advisory_study_plan_duration',
                violation_error_message=_('طول برنامه باید بین ۱ و ۹۰ روز باشد.'),
            ),
            # The single draft slot. Partial on purpose: many PUBLISHED plans may
            # coexist (a rolling calendar), but the scratch space is one row the
            # planner form owns outright.
            models.UniqueConstraint(
                fields=['engagement'],
                condition=models.Q(status='DRAFT'),
                name='uniq_advisory_study_plan_draft_slot',
                violation_error_message=_('برای این همکاری از قبل یک پیش‌نویس وجود دارد.'),
            ),
        ]
        indexes = [
            # The shape of every read: "this engagement's plans by status, in
            # calendar order" — the advisor's list and the feed's intersection
            # filter both walk exactly this index.
            models.Index(
                fields=['engagement', 'status', 'start_date'],
                name='idx_adv_plan_eng_status_start',
            ),
        ]
        verbose_name = _('برنامه‌ی مطالعه')
        verbose_name_plural = _('برنامه‌های مطالعه')

    def __str__(self) -> str:
        return f'{self.start_date}+{self.duration_days}d ({self.get_status_display()}) ← #{self.engagement_id}'

    @property
    def end_date(self):
        """The last covered day, inclusive — ``start + duration - 1``.

        A 7-day plan starting Monday covers Mon..Sun, so its end is start+6.
        Overlap comparisons (``services/study_plans``) use this same inclusive
        convention, which is what makes edge-touching plans legal.
        """
        return self.start_date + datetime.timedelta(days=self.duration_days - 1)


class StudyPlanItem(models.Model):
    """«On day N of the plan, study subject S for M minutes» (S7).

    The join key is ``StudentSubject``, the same decision ``DailyLogItem`` made
    (S8): the commitment metric divides logged minutes by planned minutes grouped
    per subject, and keying both on the selection row needs no migration to
    compute. ``PROTECT`` matches that sibling too — a selection a plan ever named
    must not be deletable out from under it (and in practice never is: S4 retires
    selections by flipping ``is_active``, never deleting).

    ``day_offset`` is relative to the plan's ``start_date`` (0-based), which is
    what makes a plan movable: shift the start, keep the items. The DB check only
    holds the absolute 0..89 bound; the real rule — strictly less than the parent
    plan's ``duration_days`` — compares across tables and therefore lives in the
    write door.

    Unlike ``DailyLogItem``, items of a **draft** are hard-replaced on every save
    and a superseded draft can be deleted outright: a draft has no history value —
    it is the advisor's unsent scratchpad, not a record of anything that happened.
    Published plans' items are the durable half and are never rewritten except by
    unpublish → re-draft.
    """

    plan = models.ForeignKey(
        StudyPlan,
        on_delete=models.PROTECT,
        related_name='items',
        verbose_name=_('برنامه'),
    )
    day_offset = models.SmallIntegerField(
        verbose_name=_('روزِ برنامه (صفر-مبنا)'),
        help_text=_('۰ یعنی همان روزِ شروع؛ باید کمتر از طول برنامه باشد.'),
    )
    student_subject = models.ForeignKey(
        StudentSubject,
        on_delete=models.PROTECT,
        related_name='plan_items',
        verbose_name=_('درسِ دانش‌آموز'),
    )
    planned_minutes = models.PositiveSmallIntegerField(
        verbose_name=_('دقیقه‌ی برنامه‌ریزی‌شده'),
        help_text=_('هم‌مقیاس با دقیقه‌ی واقعیِ گزارش روزانه، تا نسبتِ تعهد معنا داشته باشد.'),
    )
    # Restart step 4: what exactly to study, in which unit, how much of it is
    # test-solving, and the advisor's mastery color for the subject. All optional:
    # a row written before this enrichment (or without the detail) stays legal.
    topic = models.CharField(
        max_length=200,
        blank=True,
        default='',
        verbose_name=_('موضوع'),
    )
    unit_label = models.CharField(
        max_length=60,
        blank=True,
        default='',
        verbose_name=_('واحد'),
    )
    test_minutes = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(MAX_PLAN_TEST_MINUTES)],
        verbose_name=_('زمان تست'),
        help_text=_('۰ تا ۴۸۰ دقیقه؛ خالی یعنی مشاور زمانی مشخص نکرده — که با «۰» یکی نیست.'),
    )
    mastery_color = models.CharField(
        max_length=6,
        null=True,
        blank=True,
        choices=MASTERY_COLOR_CHOICES,
        verbose_name=_('رنگ تسلط'),
    )
    # Research wave (2026-08-31): optional HH:MM so the advisor can place the
    # row inside the student's day (the «پارت‌بندی» every planning form uses).
    # Null = «هر ساعتِ آن روز» — the pre-field meaning, unchanged.
    start_time = models.TimeField(
        null=True,
        blank=True,
        verbose_name=_('ساعت شروع'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['day_offset', 'student_subject__subject__name']
        constraints = [
            models.UniqueConstraint(
                fields=['plan', 'day_offset', 'student_subject'],
                name='uniq_advisory_plan_item_row',
                violation_error_message=_('برای هر روز و درس فقط یک ردیف بفرستید.'),
            ),
            models.CheckConstraint(
                condition=models.Q(
                    day_offset__gte=0,
                    day_offset__lte=MAX_PLAN_DAY_OFFSET,
                ),
                name='ck_advisory_plan_item_day_offset',
                violation_error_message=_('روزِ برنامه باید بین ۰ و ۸۹ باشد.'),
            ),
            models.CheckConstraint(
                condition=models.Q(
                    planned_minutes__gte=1,
                    planned_minutes__lte=MAX_PLAN_MINUTES_PER_ITEM,
                ),
                name='ck_advisory_plan_item_minutes',
                violation_error_message=_('دقیقه‌ی برنامه‌ریزی‌شده باید بین ۱ تا ۹۶۰ باشد.'),
            ),
        ]
        verbose_name = _('ردیف برنامه')
        verbose_name_plural = _('ردیف‌های برنامه')

    def __str__(self) -> str:
        return f'day {self.day_offset}: {self.student_subject_id} {self.planned_minutes}د'


class AdvisoryAccessLog(models.Model):
    """One append-only line: *someone read this engagement's data* (D4).

    From the moment reading leaves the pair who already know the data — i.e. from
    step 6's advisor feed — the read itself is recorded. Nothing reads this table
    through the API and nothing edits it: it exists so that «who looked at this
    student, when» has an answer that does not depend on anyone's memory, and so a
    future audit surface inherits rows from day one (there is deliberately no
    backfill — before this table existed, reads were simply unlogged).

    ``reader`` is ``SET_NULL``: a deleted account must not take the evidence of
    its reads with it. ``engagement`` is ``PROTECT``: the log is about that
    relationship and must outlive any attempt to tidy it away. The admin page is
    fully read-only — an editable audit trail is a contradiction.
    """

    reader = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        verbose_name=_('خواننده'),
    )
    engagement = models.ForeignKey(
        AdvisoryEngagement,
        on_delete=models.PROTECT,
        related_name='access_logs',
        verbose_name=_('همکاری'),
    )
    action = models.CharField(
        max_length=32,
        verbose_name=_('کنش'),
        help_text=_("مثلاً 'study_feed_view' — باز کردن فید مطالعه توسط مشاور."),
    )
    accessed_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-accessed_at']
        indexes = [
            models.Index(
                fields=['engagement', '-accessed_at'],
                name='idx_adv_accesslog_eng_time',
            ),
            models.Index(
                fields=['reader', '-accessed_at'],
                name='idx_adv_accesslog_reader_time',
            ),
        ]
        verbose_name = _('ثبت دسترسی')
        verbose_name_plural = _('ثبت‌های دسترسی')

    def __str__(self) -> str:
        return f'{self.action} ← #{self.engagement_id}'


# ── Restart wave 3 (steps 2, 7, 10): intake, weekly assessment, call log ─────
#
# Three independent modules from the restart plan (docs/features/advisor-
# restart-plan.md §۵ گام ۲ / گام ۷ / گام ۱۰), all hanging off the engagement —
# the tenancy carrier — like every advisory table before them. Reads go through
# ``services/scope.py``; writes through the three new doors ``services/intake.py``,
# ``services/assessments.py`` and ``services/calls.py`` (each pinned in
# ``test_import_boundaries``' exempt list).


def _validate_saturday_week_start(value):
    """Model-level guard converting ``calendar.ensure_saturday``'s ValueError.

    ق۴: the Saturday formula is written once in ``services/calendar.py`` and
    every week-anchored column validates through it — never a local copy. The
    wrapper only translates the exception type so Django field validation (and
    therefore the admin) can surface it as a normal ``ValidationError``.
    """
    try:
        ensure_saturday(value)
    except ValueError as exc:
        raise ValidationError(_('تاریخ باید شنبه باشد.')) from exc


# The Iranian school week: 0 = شنبه … 6 = جمعه. The wire sends the raw int;
# these labels exist for the admin and for any server-side rendering.
INTAKE_WEEKDAY_CHOICES = [
    (0, _('شنبه')),
    (1, _('یکشنبه')),
    (2, _('دوشنبه')),
    (3, _('سه‌شنبه')),
    (4, _('چهارشنبه')),
    (5, _('پنج‌شنبه')),
    (6, _('جمعه')),
]


class AdvisoryIntakeProfile(models.Model):
    """The digital «اطلاعات فردی دانش‌آموز» page (restart step 2, PDF ص۱).

    One row per engagement (OneToOne) holding the student's context an advisor
    needs before planning: school, city, last year's GPA, target major and
    university, mock-exam institute, and how many minutes of self-directed
    study a free day holds. The class timetable lives in
    ``AdvisoryIntakeClass`` rows under ``classes``.

    The row is created lazily by ``services.intake.get_or_init_intake`` — a
    never-filled form reads back as the all-empty default payload, not a 404.
    ``updated_by`` records whoever saved last (advisor *or* student; both may
    write this form) and is ``SET_NULL`` per ق۷: deleting an account must not
    delete the fact that the form was filled.
    """

    engagement = models.OneToOneField(
        AdvisoryEngagement,
        on_delete=models.CASCADE,
        related_name='intake',
        verbose_name=_('همکاری'),
    )
    school = models.CharField(
        max_length=120,
        blank=True,
        default='',
        verbose_name=_('مدرسه'),
    )
    city = models.CharField(
        max_length=60,
        blank=True,
        default='',
        verbose_name=_('شهر'),
    )
    # Nullable, not defaulted: «معدل سال گذشته را نگرفته‌ام» must stay distinct
    # from an honest «۰». The 0..20 band mirrors the Iranian grading scale.
    last_gpa = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(20)],
        verbose_name=_('معدل سال گذشته'),
        help_text=_('عددی بین ۰ تا ۲۰؛ خالی یعنی ثبت نشده.'),
    )
    target_major = models.CharField(
        max_length=120,
        blank=True,
        default='',
        verbose_name=_('رشتهٔ هدف'),
    )
    target_university = models.CharField(
        max_length=120,
        blank=True,
        default='',
        verbose_name=_('دانشگاه هدف'),
    )
    mock_exam_institute = models.CharField(
        max_length=120,
        blank=True,
        default='',
        verbose_name=_('مؤسسۀ آزمون آزمایشی'),
    )
    # A free day holds at most 1440 minutes — the same physical bound the daily
    # log's day ceiling uses, so no answer here can promise more than a day has.
    free_day_minutes = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(1440)],
        verbose_name=_('میانگین مطالعۀ روز آزاد (دقیقه)'),
        help_text=_('۰ تا ۱۴۴۰ دقیقه؛ خالی یعنی ثبت نشده.'),
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='+',
        verbose_name=_('آخرین ویرایشگر'),
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('پروفایل شناخت')
        verbose_name_plural = _('پروفایل‌های شناخت')

    def __str__(self) -> str:
        return f'intake ← #{self.engagement_id}'


class AdvisoryIntakeClass(models.Model):
    """One row of the intake's weekly class timetable (restart step 2).

    Rows are rebuilt wholesale on every save (set-replace, like every advisory
    PUT) — there is no history to preserve because the table describes the
    student's *current* schedule, not a record of past terms. The row cap (10)
    is a service rule (``services.intake.MAX_INTAKE_CLASSES``), not a constraint:
    a DB check cannot count sibling rows.

    ``weekday`` follows the Iranian week with 0 = شنبه; ``start_time``/
    ``end_time`` are both optional and, when both present, must satisfy
    end > start — enforced by the write door with the Persian message.
    """

    intake = models.ForeignKey(
        AdvisoryIntakeProfile,
        on_delete=models.CASCADE,
        related_name='classes',
        verbose_name=_('پروفایل شناخت'),
    )
    name = models.CharField(
        max_length=120,
        verbose_name=_('نام کلاس'),
    )
    teacher = models.CharField(
        max_length=120,
        blank=True,
        default='',
        verbose_name=_('دبیر'),
    )
    weekday = models.PositiveSmallIntegerField(
        choices=INTAKE_WEEKDAY_CHOICES,
        verbose_name=_('روز هفته'),
        help_text=_('۰ = شنبه تا ۶ = جمعه.'),
    )
    start_time = models.TimeField(
        null=True,
        blank=True,
        verbose_name=_('ساعت شروع'),
    )
    end_time = models.TimeField(
        null=True,
        blank=True,
        verbose_name=_('ساعت پایان'),
    )
    order = models.PositiveSmallIntegerField(
        default=0,
        verbose_name=_('ترتیب'),
    )

    class Meta:
        ordering = ['order', 'id']
        verbose_name = _('کلاس شناخت')
        verbose_name_plural = _('کلاس‌های شناخت')

    def __str__(self) -> str:
        return f'{self.name} ({self.weekday}) ← #{self.intake_id}'



class WeeklyAssessment(models.Model):
    """One week of the advisor's 15-criteria assessment (restart step 7, PDF ص۱۰).

    The advisor scores the student 1..5 on each of the fifteen criteria listed
    in ``services.assessments.WEEKLY_ASSESSMENT_CRITERIA`` — the single source
    both the validation and the wire's ``criteria`` list read — plus a free-text
    summary. ``scores`` is a JSON object ``{"<code>": 1..5}`` rather than fifteen
    columns because the criterion set is a stable *contract* (codes are JSON
    keys; changing one after launch is a data migration), not a schema question.

    This is advisor-internal by locked decision: **no student route exists**
    (گام ۷: «سمت دانش‌آموز: هیچ روت»). One row per ``(engagement, week_start)``
    via the unique constraint below; re-saving a week is an update, never a
    second row.
    """

    engagement = models.ForeignKey(
        AdvisoryEngagement,
        on_delete=models.CASCADE,
        related_name='weekly_assessments',
        verbose_name=_('همکاری'),
    )
    # Saturday-anchored (ق۴) and validated at the column level through
    # ``calendar.ensure_saturday`` so no code path can store a mid-week anchor.
    week_start = models.DateField(
        validators=[_validate_saturday_week_start],
        verbose_name=_('شروع هفته'),
        help_text=_('شنبهٔ آغاز هفته (میلادی).'),
    )
    scores = models.JSONField(
        default=dict,
        verbose_name=_('امتیاز معیارها'),
        help_text=_('شکل: {"<code>": 1..5} برای هر ۱۵ معیار.'),
    )
    advisor_summary = models.TextField(
        blank=True,
        default='',
        verbose_name=_('جمع‌بندی مشاور'),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='+',
        verbose_name=_('ایجادکننده'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-week_start']
        constraints = [
            models.UniqueConstraint(
                fields=['engagement', 'week_start'],
                name='uniq_advisory_weekly_assessment',
                violation_error_message=_('برای این هفته از قبل ارزیابی ثبت شده است.'),
            ),
        ]
        verbose_name = _('ارزیابی هفتگی')
        verbose_name_plural = _('ارزیابی‌های هفتگی')

    def __str__(self) -> str:
        return f'{self.week_start} ← #{self.engagement_id}'



class WeeklyCallLog(models.Model):
    """One week of the advisor's weekly-call checklist (restart step 10, PDF ص۳۸).

    A stored row records what actually happened on that week's call (done,
    date, topic as possibly edited by the advisor, note). Weeks with **no**
    row are not missing data — ``services.calls.list_call_logs`` materializes
    them virtually with the rotating default topic for that engagement-week,
    and a stored topic always wins over the default. Like the weekly
    assessment this is advisor-internal: **no student route exists**.

    Absent optional keys on PUT keep the stored values (upsert semantics), so
    the advisor can tick «انجام شد» without retyping the note.
    """

    engagement = models.ForeignKey(
        AdvisoryEngagement,
        on_delete=models.CASCADE,
        related_name='call_logs',
        verbose_name=_('همکاری'),
    )
    # Same Saturday anchor rule as WeeklyAssessment — one formula, one validator.
    week_start = models.DateField(
        validators=[_validate_saturday_week_start],
        verbose_name=_('شروع هفته'),
        help_text=_('شنبهٔ آغاز هفته (میلادی).'),
    )
    done = models.BooleanField(
        default=False,
        verbose_name=_('انجام شد'),
    )
    call_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('تاریخ تماس'),
    )
    topic = models.CharField(
        max_length=200,
        blank=True,
        default='',
        verbose_name=_('موضوع'),
    )
    note = models.TextField(
        blank=True,
        default='',
        verbose_name=_('یادداشت'),
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-week_start']
        constraints = [
            models.UniqueConstraint(
                fields=['engagement', 'week_start'],
                name='uniq_advisory_weekly_call_log',
                violation_error_message=_('برای این هفته از قبل تماسی ثبت شده است.'),
            ),
        ]
        verbose_name = _('تماس هفتگی')
        verbose_name_plural = _('تماس‌های هفتگی')

    def __str__(self) -> str:
        return f'{self.week_start} call ← #{self.engagement_id}'


# ── Restart wave 4 (steps 5, 6): exam scores and exam analyses ───────────────
#
# Two modules from the restart plan (docs/features/advisor-restart-plan.md
# §۵ گام ۵ / گام ۶), both hanging off the engagement — the tenancy carrier —
# like every advisory table before them. Reads resolve through
# ``services/scope.py``; every write goes through the single door
# ``services/exam_records.py`` (pinned in ``test_import_boundaries``' exempt
# list). Step 6 builds directly on step 5's files: same door, same module.

# Restart step 5 (PDF ص۴۲): what kind of exam a score row describes.
# ``CLASS_C`` (the trailing C disambiguates from the platform-wide ``Class``
# concept) is a konkur-prep institute class exam.
EXAM_KIND_CHOICES = [
    ('SCHOOL', _('مدرسه')),
    ('PERSONAL', _('شخصی')),
    ('CLASS_C', _('کلاس')),
    ('ONLINE', _('آنلاین')),
    ('NATIONAL', _('کنکور کشوری')),
    ('ADVISOR', _('آزمون مشاور')),
]

# The advisor's qualitative verdict on one exam (restart step 5).
ADVISOR_RATING_CHOICES = [
    ('EXCELLENT', _('عالی')),
    ('GOOD', _('خوب')),
    ('FAIR', _('متوسط')),
    ('WEAK', _('ضعیف')),
]


class StudyExamScore(models.Model):
    """One row of the «نمرات کسب‌شده» table (restart step 5, PDF ص۴۲).

    One exam with its kind, percent, تراز, date and the advisor's verdict.
    Rows hang off the engagement and are capped at
    ``services.exam_records.MAX_EXAM_SCORES`` per engagement — a service rule,
    not a constraint, because a DB check cannot count sibling rows.

    ``subject`` is an *optional* link into the catalog (``PROTECT``, like every
    other reference to ``Subject``): most rows name their exam freely in
    ``title`` and only some map onto a catalog row. ``created_by`` records
    which advisor entered the row (``SET_NULL`` per ق۷).
    """

    engagement = models.ForeignKey(
        AdvisoryEngagement,
        on_delete=models.CASCADE,
        related_name='exam_scores',
        verbose_name=_('همکاری'),
    )
    title = models.CharField(
        max_length=120,
        verbose_name=_('عنوان آزمون'),
        help_text=_('نام آزادِ آزمون یا درس، همان‌طور که مشاور می‌نویسد.'),
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='+',
        verbose_name=_('درس'),
        help_text=_('پیوند اختیاری به کاتالوگ درس؛ خالی یعنی بدون پیوند.'),
    )
    exam_kind = models.CharField(
        max_length=10,
        choices=EXAM_KIND_CHOICES,
        verbose_name=_('نوع آزمون'),
    )
    exam_date = models.DateField(
        verbose_name=_('تاریخ آزمون'),
        help_text=_('میلادی؛ نمایش شمسی در فرانت‌اند.'),
    )
    score_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name=_('درصد'),
    )
    # Nullable, not defaulted: «تراز ثبت نشده» must stay distinct from «۰».
    tara = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_('تراز کل'),
    )
    advisor_rating = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        choices=ADVISOR_RATING_CHOICES,
        verbose_name=_('ارزیابی مشاور'),
    )
    advisor_note = models.TextField(
        blank=True,
        default='',
        verbose_name=_('یادداشت مشاور'),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='+',
        verbose_name=_('ایجادکننده'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Newest exam first — the shape of both readers (advisor table and
        # student mirror). Matches the (engagement, -exam_date) index below so
        # the sort is index-served; ``-id`` breaks same-day ties stably.
        ordering = ['-exam_date', '-id']
        indexes = [
            models.Index(
                fields=['engagement', '-exam_date'],
                name='idx_adv_examscore_eng_date',
            ),
        ]
        verbose_name = _('نمرۀ آزمون')
        verbose_name_plural = _('نمرات آزمون')

    def __str__(self) -> str:
        return f'{self.title} {self.score_percent}% ← #{self.engagement_id}'


# Restart step 6 (PDF ص۱۷-۲۰): which grade band a report card belongs to.
GRADE_BAND_CHOICES = [
    ('G10', _('دهم')),
    ('G11', _('یازدهم')),
    ('G12S1', _('دوازدهم نیمسال اول')),
    ('G12S2', _('دوازدهم نیمسال دوم')),
]

# The answer-sheet bound (PDF ص۴۳-۴۴): question numbers are 1..300. The model
# validator holds the absolute band; the duplicate rule comparing sibling notes
# lives in the write door.
MAX_ANALYSIS_QUESTION_NUMBER = 300


class StudyExamAnalysis(models.Model):
    """One post-exam report-card analysis (restart step 6, PDF ص۱۷-۲۰).

    The کارنامه metrics (تراز/رتبه‌ها/درصدها/دلتا) plus the advisor's free-text
    report. Every metric column is nullable — an institute's report card rarely
    fills every box, and «ثبت نشده» must stay distinct from «۰» everywhere.
    The per-subject rows and per-question notes live in ``rows``/``notes`` and
    are replaced wholesale on every save by ``services.exam_records``.

    Unlike the score rows above there is no ``created_by``: the analysis is a
    living document of the engagement, not an attributed entry.
    """

    engagement = models.ForeignKey(
        AdvisoryEngagement,
        on_delete=models.CASCADE,
        related_name='exam_analyses',
        verbose_name=_('همکاری'),
    )
    exam_number = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name=_('شمارهٔ آزمون'),
    )
    exam_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('تاریخ آزمون'),
        help_text=_('میلادی؛ نمایش شمسی در فرانت‌اند.'),
    )
    grade_band = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        choices=GRADE_BAND_CHOICES,
        verbose_name=_('بازهٔ پایه'),
    )
    total_tara = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_('تراز کل'),
    )
    national_rank = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_('رتبهٔ کشوری'),
    )
    region_rank = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_('رتبهٔ منطقه'),
    )
    city_rank = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_('رتبهٔ شهر'),
    )
    highest_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name=_('بالاترین درصد'),
    )
    lowest_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name=_('پایین‌ترین درصد'),
    )
    # Signed on purpose: a negative delta («تراز نسبت به آزمون قبل کم شده») is
    # the interesting case, not an error.
    tara_delta = models.SmallIntegerField(
        null=True,
        blank=True,
        verbose_name=_('تغییر تراز'),
    )
    advisor_report = models.TextField(
        blank=True,
        default='',
        verbose_name=_('گزارش مشاور'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-exam_date', '-id']
        verbose_name = _('تحلیل آزمون')
        verbose_name_plural = _('تحلیل‌های آزمون')

    def __str__(self) -> str:
        return f'analysis {self.exam_date or self.pk} ← #{self.engagement_id}'


class StudyExamAnalysisRow(models.Model):
    """One subject's line of an analysis: غلط/نزده/شک‌دار + علت (step 6).

    ``subject_name`` is free text, not a catalog FK — each institute names its
    own subjects on the report card, and forcing them into the national catalog
    would corrupt both. The doubtful counters are each bounded by their row's
    ``doubtful_total``; that comparison spans sibling columns of one row's
    payload, so it is a write-door rule, not a constraint.
    """

    analysis = models.ForeignKey(
        StudyExamAnalysis,
        on_delete=models.CASCADE,
        related_name='rows',
        verbose_name=_('تحلیل'),
    )
    subject_name = models.CharField(
        max_length=120,
        verbose_name=_('نام درس'),
    )
    wrong_count = models.PositiveIntegerField(default=0, verbose_name=_('غلط'))
    skipped_count = models.PositiveIntegerField(default=0, verbose_name=_('نزده'))
    doubtful_total = models.PositiveIntegerField(default=0, verbose_name=_('شک‌دار کل'))
    doubtful_wrong = models.PositiveIntegerField(default=0, verbose_name=_('شک‌دار غلط'))
    doubtful_skipped = models.PositiveIntegerField(default=0, verbose_name=_('شک‌دار نزده'))
    doubtful_correct = models.PositiveIntegerField(default=0, verbose_name=_('شک‌دار درست'))
    cause_note = models.CharField(
        max_length=300,
        blank=True,
        default='',
        verbose_name=_('علت'),
    )

    class Meta:
        # Insertion order: the advisor wrote the rows in a deliberate order.
        ordering = ['id']
        verbose_name = _('ردیف تحلیل درس')
        verbose_name_plural = _('ردیف‌های تحلیل')

    def __str__(self) -> str:
        return f'{self.subject_name} ← #{self.analysis_id}'


class StudyExamAnalysisNote(models.Model):
    """One «نکتهٔ مهم» pinned to a single question number (step 6, ص۳۵-۳۶).

    One note per (analysis, question): two notes on the same question are a
    data-entry mistake the wire rejects with a Persian message naming the
    question, enforced by the write door ahead of the constraint below.
    """

    analysis = models.ForeignKey(
        StudyExamAnalysis,
        on_delete=models.CASCADE,
        related_name='notes',
        verbose_name=_('تحلیل'),
    )
    question_number = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(1),
            MaxValueValidator(MAX_ANALYSIS_QUESTION_NUMBER),
        ],
        verbose_name=_('شمارهٔ سؤال'),
    )
    subject_name = models.CharField(
        max_length=120,
        verbose_name=_('نام درس'),
    )
    note = models.TextField(
        blank=True,
        default='',
        verbose_name=_('یادداشت'),
    )

    class Meta:
        ordering = ['question_number']
        constraints = [
            models.UniqueConstraint(
                fields=['analysis', 'question_number'],
                name='uniq_advisory_analysis_note_question',
                violation_error_message=_('برای هر سؤال فقط یک یادداشت بفرستید.'),
            ),
        ]
        verbose_name = _('یادداشت سؤال')
        verbose_name_plural = _('یادداشت‌های سؤال')

    def __str__(self) -> str:
        return f'q{self.question_number} ← #{self.analysis_id}'


# ── Restart wave 5 (step 8): the monthly outlook + month strategies ──────────
#
# One module from the restart plan (docs/features/advisor-restart-plan.md
# §۵ گام ۸), hanging off the engagement — the tenancy carrier — like every
# advisory table before it. Reads resolve through ``services/scope.py``; every
# write goes through the single door ``services/monthly.py`` (pinned in
# ``test_import_boundaries``' exempt list).

# Which side of the pair executes a month strategy. The raw codes are the wire
# contract; the Persian labels are rendered client-side.
STRATEGY_EXECUTOR_CHOICES = [
    ('ADVISOR', _('مشاور')),
    ('STUDENT', _('دانش‌آموز')),
]

# The paper page (PDF ص۴) carries 4 strategy slots; the plan grants headroom to
# 10. The bound lives on ``position``'s validators below and is restated as a
# constant here so the service, serializer docs and tests read one number.
MAX_MONTHLY_STRATEGIES = 10


class MonthlyOutlook(models.Model):
    """One calendar month of «ماه در یک نگاه» (restart step 8, PDF ص۳-۴).

    The row is keyed ``(engagement, month_start)`` — but ق۵ pins what
    ``month_start`` is NOT: no Jalali math ever happens server-side. It is a
    plain Gregorian date the frontend computes (first Gregorian day of the
    Jalali month it wants to show) and hands over as an opaque ISO key. The
    server never interprets it beyond equality.

    Like the intake form, the row is created lazily by
    ``services.monthly.get_or_init_outlook`` — a never-saved month reads back
    as the all-empty payload, not a 404. Entries and strategies live in child
    tables and are replaced wholesale on every save.
    """

    engagement = models.ForeignKey(
        AdvisoryEngagement,
        on_delete=models.CASCADE,
        related_name='monthly_outlooks',
        verbose_name=_('همکاری'),
    )
    # An opaque Gregorian key (ق۵), not a semantic "month": boundary calendars
    # may legitimately reference days outside it, so nothing validates
    # membership — only uniqueness below.
    month_start = models.DateField(
        verbose_name=_('شروع ماه'),
        help_text=_('اولین روزِ میلادیِ ماه جلالی موردنظر؛ کلیدِ یکتا به‌ازای همکاری.'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-month_start']
        constraints = [
            models.UniqueConstraint(
                fields=['engagement', 'month_start'],
                name='uniq_advisory_monthly_outlook',
                violation_error_message=_('برای این ماه از قبل برنامه‌ای ثبت شده است.'),
            ),
        ]
        verbose_name = _('برنامهٔ ماه')
        verbose_name_plural = _('برنامه‌های ماه')

    def __str__(self) -> str:
        return f'{self.month_start} ← #{self.engagement_id}'


class MonthlyOutlookEntry(models.Model):
    """One day's line of the monthly outlook: مناسبت + تقویم تحصیلی + کارها.

    Rows are rebuilt wholesale on every save (set-replace, like every advisory
    PUT). ``date`` is deliberately **not** constrained to fall inside the parent
    outlook's month: boundary calendars legitimately carry days from the edges
    of neighbouring Jalali months, and ق۵ forbids the server from having an
    opinion about where a Jalali month ends. Uniqueness per day is the only rule.
    """

    outlook = models.ForeignKey(
        MonthlyOutlook,
        on_delete=models.CASCADE,
        related_name='entries',
        verbose_name=_('برنامهٔ ماه'),
    )
    date = models.DateField(
        verbose_name=_('تاریخ'),
        help_text=_('میلادی؛ لزوماً داخل همان ماه نیست (تقویم مرزی مجاز است).'),
    )
    event = models.CharField(
        max_length=120,
        blank=True,
        default='',
        verbose_name=_('مناسبت'),
    )
    academic_note = models.CharField(
        max_length=200,
        blank=True,
        default='',
        verbose_name=_('تقویم تحصیلی'),
    )
    tasks = models.TextField(
        blank=True,
        default='',
        verbose_name=_('کارها'),
    )

    class Meta:
        ordering = ['date']
        constraints = [
            models.UniqueConstraint(
                fields=['outlook', 'date'],
                name='uniq_advisory_monthly_entry',
                violation_error_message=_('برای هر روز فقط یک ردیف بفرستید.'),
            ),
        ]
        verbose_name = _('ردیف روزِ ماه')
        verbose_name_plural = _('ردیف‌های روزِ ماه')

    def __str__(self) -> str:
        return f'{self.date} ← #{self.outlook_id}'


class MonthlyStrategy(models.Model):
    """One slot of «استراتژی‌های ماه»: who executes what, and how (PDF ص۴).

    ``position`` orders the slots on the page and is unique per outlook — two
    rows claiming slot 3 are a data-entry mistake the wire rejects with a
    Persian message ahead of the constraint below. The 1..10 band is held by
    the column validators; the duplicate rule comparing sibling rows lives in
    the write door.
    """

    outlook = models.ForeignKey(
        MonthlyOutlook,
        on_delete=models.CASCADE,
        related_name='strategies',
        verbose_name=_('برنامهٔ ماه'),
    )
    position = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(1),
            MaxValueValidator(MAX_MONTHLY_STRATEGIES),
        ],
        verbose_name=_('پوزیشن'),
        help_text=_('بین ۱ تا ۱۰؛ ترتیب نمایش اسلات‌ها در صفحه.'),
    )
    title = models.CharField(
        max_length=120,
        verbose_name=_('عنوان'),
    )
    executor = models.CharField(
        max_length=10,
        choices=STRATEGY_EXECUTOR_CHOICES,
        verbose_name=_('مجری'),
    )
    body = models.TextField(
        blank=True,
        default='',
        verbose_name=_('شرح'),
    )

    class Meta:
        ordering = ['position']
        constraints = [
            models.UniqueConstraint(
                fields=['outlook', 'position'],
                name='uniq_advisory_monthly_strategy',
                violation_error_message=_('برای هر پوزیشن فقط یک استراتژی مجاز است.'),
            ),
        ]
        verbose_name = _('استراتژی ماه')
        verbose_name_plural = _('استراتژی‌های ماه')

    def __str__(self) -> str:
        return f'#{self.position} {self.title} ← #{self.outlook_id}'


# ── Restart wave 5 (step 9): the 7-day study challenge ───────────────────────
#
# One module from the restart plan (docs/features/advisor-restart-plan.md
# §۵ گام ۹), hanging off the engagement — the tenancy carrier — like every
# advisory table before it. Reads resolve through ``services/scope.py``; every
# write goes through the single door ``services/challenges.py`` (pinned in
# ``test_import_boundaries``' exempt list).

# The challenge lifecycle. Terminal states are terminal: only ACTIVE may move
# to DONE/CANCELLED, and nothing moves back — that guard is a service rule
# (``services.challenges``) because it compares a row's old and new status,
# which no column-level constraint can see.
CHALLENGE_STATUS_CHOICES = [
    ('ACTIVE', _('فعال')),
    ('DONE', _('پایان‌یافته')),
    ('CANCELLED', _('لغوشده')),
]

# The paper form (PDF ص۳۷) is one week wide: day 1..7. The horizon is fixed by
# design — ``end_date`` is always ``start_date + 6 days``, computed by the
# write door and never accepted from the client.
MAX_CHALLENGE_DAYS = 7

# A service ceiling (not a constraint — a DB check cannot count sibling rows):
# at most this many challenges per engagement may sit in ACTIVE at once.
MAX_ACTIVE_CHALLENGES = 3


class StudyChallenge(models.Model):
    """One 7-day challenge the advisor sets and the student fills in daily.

    The advisor owns the frame (title, goal, routine, observer, problem
    target, start date); the student owns the per-day rows under ``days``.
    ``end_date`` is deliberately NOT writable from the wire: it is derived as
    ``start_date + 6 days`` on every save so the seven-day shape cannot drift.
    Status flows one way::

        ACTIVE ──▶ DONE        (finished)
               └─▶ CANCELLED   (abandoned)

    There is no path back to ACTIVE — a finished challenge is history, and
    re-running it means creating a new one.
    """

    engagement = models.ForeignKey(
        AdvisoryEngagement,
        on_delete=models.CASCADE,
        related_name='challenges',
        verbose_name=_('همکاری'),
    )
    title = models.CharField(
        max_length=120,
        verbose_name=_('عنوان چالش'),
    )
    goal_text = models.TextField(
        blank=True,
        default='',
        verbose_name=_('تعریف و هدف'),
    )
    daily_routine = models.CharField(
        max_length=200,
        blank=True,
        default='',
        verbose_name=_('روتین روزانه'),
    )
    execution_note = models.CharField(
        max_length=200,
        blank=True,
        default='',
        verbose_name=_('نوع اجرا'),
    )
    observer = models.CharField(
        max_length=120,
        blank=True,
        default='',
        verbose_name=_('مجری و ناظر'),
    )
    problem_target = models.TextField(
        blank=True,
        default='',
        verbose_name=_('مشکل و نتیجهٔ مدنظر'),
    )
    start_date = models.DateField(
        verbose_name=_('تاریخ شروع'),
        help_text=_('میلادی؛ پایان همیشه ششمین روز بعد است.'),
    )
    # Server-computed (see the write door): never accepted from the client.
    end_date = models.DateField(
        editable=False,
        verbose_name=_('تاریخ پایان'),
        help_text=_('ششمین روز پس از شروع؛ توسط سرور محاسبه می‌شود.'),
    )
    status = models.CharField(
        max_length=10,
        choices=CHALLENGE_STATUS_CHOICES,
        default='ACTIVE',
        db_index=True,
        verbose_name=_('وضعیت'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date', '-id']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gt=models.F('start_date')),
                name='ck_advisory_challenge_dates',
                violation_error_message=_('تاریخ پایان باید بعد از تاریخ شروع باشد.'),
            ),
        ]
        indexes = [
            models.Index(
                fields=['engagement', 'status'],
                name='idx_adv_challenge_eng_status',
            ),
        ]
        verbose_name = _('چالش هفت‌روزه')
        verbose_name_plural = _('چالش‌های هفت‌روزه')

    def __str__(self) -> str:
        return f'{self.title} [{self.status}] ← #{self.engagement_id}'


class StudyChallengeDay(models.Model):
    """One day of a challenge: the student's goal for it and what happened.

    Rows are rebuilt wholesale on every save of the days route (set-replace).
    Both sides write here but under different rules enforced by the door: the
    advisor may rewrite everything, while the student may only ever set
    ``goal`` and ``summary`` — never the day numbering itself.
    """

    challenge = models.ForeignKey(
        StudyChallenge,
        on_delete=models.CASCADE,
        related_name='days',
        verbose_name=_('چالش'),
    )
    day_number = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(1),
            MaxValueValidator(MAX_CHALLENGE_DAYS),
        ],
        verbose_name=_('شمارهٔ روز'),
        help_text=_('بین ۱ تا ۷.'),
    )
    goal = models.CharField(
        max_length=200,
        blank=True,
        default='',
        verbose_name=_('هدف‌گذاری روز'),
    )
    summary = models.TextField(
        blank=True,
        default='',
        verbose_name=_('خلاصۀ کارها/مشکلات/نتیجه'),
    )

    class Meta:
        ordering = ['day_number']
        constraints = [
            models.UniqueConstraint(
                fields=['challenge', 'day_number'],
                name='uniq_advisory_challenge_day',
                violation_error_message=_('برای هر روز فقط یک ردیف بفرستید.'),
            ),
        ]
        verbose_name = _('روزِ چالش')
        verbose_name_plural = _('روزهای چالش')

    def __str__(self) -> str:
        return f'day {self.day_number} ← #{self.challenge_id}'


# ── Risman phase R (step 1): advisor-owned student folders ───────────────────
#
# One module from docs/features/risman-parity-roadmap.md §۵ گام ۱. A folder is
# the advisor's private label for grouping their own roster; it never crosses
# advisors (uniqueness is per ``(advisor, name)`` below) and never reaches the
# student side. Like every advisory table it is tenancy-bearing: reads resolve
# through ``services/scope.py`` and writes through ``services/folders.py``
# (pinned in ``test_import_boundaries``' exempt list).

MAX_FOLDER_NAME_CHARS = 64


class AdvisoryStudentFolder(models.Model):
    """A named folder an advisor groups their roster into (risman step 1).

    Ownership is absolute and single-level: ``advisor`` is the whole of the
    authorization question, answered by ``services.folders.get_folder`` — a
    foreign or unknown id is a 404, never a 403, so one advisor cannot even
    confirm another's folder names exist. Deleting a folder does NOT delete
    the engagements inside it (ق۷): the write door nulls ``engagement.folder``
    in the same transaction before the row goes.
    """

    advisor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='advisory_folders',
        verbose_name=_('مشاور'),
    )
    name = models.CharField(
        max_length=MAX_FOLDER_NAME_CHARS,
        verbose_name=_('نام پوشه'),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name', 'id']
        constraints = [
            # Two folders with one name inside one advisor's panel are a data-
            # entry mistake, not two folders. Across advisors the same name is
            # fine — folders are private labels, not a shared taxonomy.
            models.UniqueConstraint(
                fields=['advisor', 'name'],
                name='uniq_advisory_student_folder',
                violation_error_message=_('پوشه‌ای با این نام دارید.'),
            ),
        ]
        verbose_name = _('پوشهٔ دانش‌آموزان')
        verbose_name_plural = _('پوشه‌های دانش‌آموزان')

    def __str__(self) -> str:
        return f'{self.name} ← #{self.advisor_id}'


# ── Research wave (2026-08-31): goal, mistake log, topic progress ─────────────
#
# The three gaps every Iranian consultant covers but the restart plan did not:
# a stated destination (goal), the mistake notebook (دفتر اشتباهات) and per-
# topic coverage (پوشش مبحث). All three are student-owned and tenancy-bearing
# like the rest of the app; the advisor reads them through the same engagement
# join and will surface in the advisor cockpit in a later wave.

MAX_GOAL_TEXT_CHARS = 120


class AdvisoryGoal(models.Model):
    """The student's stated destination — one row per engagement.

    Every Iranian planning interview starts here (رشته/دانشگاه/رتبهٔ هدف and the
    gap to it); this is the first time the answer has a column to live in. Free
    text on purpose: rank targets like «زیر ۱۰۰۰ کشوری» are not numbers a formula
    should parse. ``updated_by`` records who last wrote it (student aspiration or
    advisor refinement) — no permission branches on it in this wave.
    """

    engagement = models.OneToOneField(
        AdvisoryEngagement,
        on_delete=models.CASCADE,
        related_name='goal',
        verbose_name=_('همکاری'),
    )
    target_title = models.CharField(
        max_length=MAX_GOAL_TEXT_CHARS,
        verbose_name=_('هدف'),
        help_text=_('مثل: پزشکی، دانشگاه شهید بهشتی'),
    )
    target_rank = models.CharField(
        max_length=60,
        blank=True,
        default='',
        verbose_name=_('رتبه/تراز هدف'),
    )
    current_rank = models.CharField(
        max_length=60,
        blank=True,
        default='',
        verbose_name=_('رتبه/تراز فعلی'),
    )
    note = models.TextField(
        blank=True,
        default='',
        verbose_name=_('یادداشت مسیر'),
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='advisory_goals_written',
        verbose_name=_('آخرین ویرایش‌گر'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('هدف تحصیلی')
        verbose_name_plural = _('اهداف تحصیلی')

    def __str__(self) -> str:
        return f'{self.target_title} ← #{self.engagement_id}'


MAX_MISTAKE_TEXT_CHARS = 300


class MistakeEntry(models.Model):
    """One row of the student's mistake notebook (دفتر اشتباهات).

    Shape follows the canonical Iranian form (hamtahsil's six-category table):
    status captures غلط/درستِ شک‌دار/نزده (a doubt-right answer is data too),
    ``error_type`` is the six-way root-cause taxonomy, and the fix trio
    (cause/fix_note/next_action) is what turns a mistake into a plan. Rows are
    student-owned; ``is_resolved`` is the student closing the loop after an
    active-recall review, not a delete.
    """

    class Status(models.TextChoices):
        WRONG = 'WRONG', _('غلط')
        DOUBT_RIGHT = 'DOUBT_RIGHT', _('درست اما شک‌دار')
        UNANSWERED = 'UNANSWERED', _('نزده')

    class ErrorType(models.TextChoices):
        CONCEPT = 'CONCEPT', _('مفهومی')
        FORGET = 'FORGET', _('فراموشی')
        METHOD = 'METHOD', _('تشخیص روش')
        EXECUTION = 'EXECUTION', _('محاسباتی/اجرایی')
        READING = 'READING', _('خواندن سؤال')
        TIME = 'TIME', _('مدیریت زمان')

    class Priority(models.TextChoices):
        HIGH = 'HIGH', _('بالا')
        MEDIUM = 'MEDIUM', _('متوسط')
        LOW = 'LOW', _('کم')

    engagement = models.ForeignKey(
        AdvisoryEngagement,
        on_delete=models.CASCADE,
        related_name='mistakes',
        verbose_name=_('همکاری'),
    )
    student_subject = models.ForeignKey(
        StudentSubject,
        on_delete=models.PROTECT,
        related_name='mistake_entries',
        verbose_name=_('درسِ دانش‌آموز'),
    )
    topic = models.CharField(
        max_length=200,
        verbose_name=_('مبحث'),
    )
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.WRONG,
        verbose_name=_('وضعیت پاسخ'),
    )
    error_type = models.CharField(
        max_length=12,
        choices=ErrorType.choices,
        verbose_name=_('نوع خطا'),
    )
    cause = models.CharField(
        max_length=MAX_MISTAKE_TEXT_CHARS,
        blank=True,
        default='',
        verbose_name=_('علت اصلی'),
    )
    fix_note = models.CharField(
        max_length=MAX_MISTAKE_TEXT_CHARS,
        blank=True,
        default='',
        verbose_name=_('نکتهٔ اصلاحی'),
    )
    next_action = models.CharField(
        max_length=MAX_MISTAKE_TEXT_CHARS,
        blank=True,
        default='',
        verbose_name=_('اقدام بعدی'),
    )
    priority = models.CharField(
        max_length=8,
        choices=Priority.choices,
        default=Priority.MEDIUM,
        verbose_name=_('اولویت'),
    )
    source_ref = models.CharField(
        max_length=120,
        blank=True,
        default='',
        verbose_name=_('منبع/شماره سؤال'),
    )
    review_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('تاریخ مرور'),
    )
    is_resolved = models.BooleanField(
        default=False,
        verbose_name=_('رفع شده'),
    )
    # Wave 6b (2026-08-31): when the student closed the loop. Null while open,
    # set on the FIRST is_resolved=True transition (services/mistakes), cleared
    # again on un-resolve. Migration 0021 backfills pre-existing resolved rows
    # from ``updated_at`` — the best available proxy for when they were closed.
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('زمان رفع'),
        help_text=_('لحظهٔ اولین رفع؛ با بازگشتن به حالت رفع‌نشده پاک می‌شود.'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['is_resolved', '-created_at']
        indexes = [
            models.Index(
                fields=['engagement', 'is_resolved', '-created_at'],
                name='idx_adv_mistakes_eng_open',
            ),
        ]
        verbose_name = _('خطای دفتر اشتباهات')
        verbose_name_plural = _('ردیف‌های دفتر اشتباهات')

    def __str__(self) -> str:
        return f'{self.get_error_type_display()} · {self.topic} ← #{self.engagement_id}'


class TopicProgress(models.Model):
    """One topic of one subject and where the student stands on it.

    The lightweight پوشش مبحث: the topic list is grown by the student/advisor
    as rows — free text, or (wave 7) linked to a leaf of the official syllabus
    tree via ``syllabus_topic`` — each carrying a status on the NEW → STUDIED →
    NEEDS_REVIEW → MASTERED ladder. ``next_review_at`` is the spaced-review
    hook — set it when a topic goes to NEEDS_REVIEW and the analytics endpoint
    surfaces everything due.
    """

    class Status(models.TextChoices):
        NEW = 'NEW', _('شروع‌نشده')
        STUDIED = 'STUDIED', _('خوانده‌شده')
        NEEDS_REVIEW = 'NEEDS_REVIEW', _('نیاز به مرور')
        MASTERED = 'MASTERED', _('تسلط‌یافته')

    engagement = models.ForeignKey(
        AdvisoryEngagement,
        on_delete=models.CASCADE,
        related_name='topic_progress',
        verbose_name=_('همکاری'),
    )
    student_subject = models.ForeignKey(
        StudentSubject,
        on_delete=models.PROTECT,
        related_name='topic_progress',
        verbose_name=_('درسِ دانش‌آموز'),
    )
    topic = models.CharField(
        max_length=200,
        verbose_name=_('مبحث'),
    )
    # Wave 7 (2026-08-31): optional link to a leaf of the official syllabus
    # tree (درخت بودجه‌بندی). The free-text ``topic`` above stays the source of
    # truth for display; when the link is set, the write door mirrors the tree
    # node's title into it, so a row can never disagree with the tree it came
    # from. ``SET_NULL``: re-seeding or dropping a tree node must not erase the
    # student's progress — the row falls back to its mirrored title.
    syllabus_topic = models.ForeignKey(
        'SyllabusTopic',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='progress_rows',
        verbose_name=_('مبحث درخت بودجه‌بندی'),
        help_text=_('پیوند اختیاری به درخت بودجه‌بندی؛ خالی یعنی متن آزاد.'),
    )
    status = models.CharField(
        max_length=14,
        choices=Status.choices,
        default=Status.NEW,
        verbose_name=_('وضعیت'),
    )
    next_review_at = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('مرور بعدی'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['student_subject__subject__name', 'topic']
        constraints = [
            models.UniqueConstraint(
                fields=['engagement', 'student_subject', 'topic'],
                name='uniq_advisory_topic_progress',
                violation_error_message=_('این مبحث از قبل در فهرست هست.'),
            ),
        ]
        verbose_name = _('پیشرفت مبحث')
        verbose_name_plural = _('پیشرفت مباحث')

    def __str__(self) -> str:
        return f'{self.topic} ({self.get_status_display()}) ← #{self.engagement_id}'


# ── Wave 7 (2026-08-31): the official syllabus tree (درخت بودجه‌بندی) ──────────
#
# The konkur budgeting tree is CATALOG data, like ``Subject`` itself: it hangs
# off the shared subject catalog, never off an engagement, is seeded
# platform-wide by ``seed_syllabus`` and carries no student data — which is why
# both models below sit in ``test_import_boundaries``' unscoped set beside
# ``Subject``. Students and advisors browse the tree read-only; per-student
# state lives in ``TopicProgress.syllabus_topic`` above, never here.


class SyllabusChapter(models.Model):
    """One chapter of a subject's official konkur syllabus (e.g. «حسابان»).

    Rows are created only by the seed command, keyed naturally by
    ``(subject, title)``: a re-run never duplicates a chapter and never
    clobbers an admin's reorder, exactly the contract ``seed_advisory_subjects``
    gives the subject catalog. ``PROTECT`` on ``subject`` matches every other
    reference to ``Subject`` — the tree of a subject anyone has planned against
    must not vanish from under that history.
    """

    subject = models.ForeignKey(
        Subject,
        on_delete=models.PROTECT,
        related_name='syllabus_chapters',
        verbose_name=_('درس'),
    )
    title = models.CharField(max_length=200, verbose_name=_('عنوان فصل'))
    order = models.PositiveSmallIntegerField(
        default=0,
        verbose_name=_('ترتیب'),
        help_text=_('جایگاه فصل در نمایش درخت.'),
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('زمان ایجاد'))

    class Meta:
        ordering = ['subject__name', 'order', 'title']
        constraints = [
            models.UniqueConstraint(
                fields=['subject', 'title'],
                name='uniq_syllabus_chapter_per_subject',
                violation_error_message=_('این فصل برای این درس از قبل ثبت شده است.'),
            ),
        ]
        verbose_name = _('فصل درخت بودجه‌بندی')
        verbose_name_plural = _('فصل‌های درخت بودجه‌بندی')

    def __str__(self) -> str:
        return f'{self.title} ← {self.subject}'


class SyllabusTopic(models.Model):
    """One topic of one chapter — the leaf of the syllabus tree.

    ``konkur_weight`` is the approximate konkur question count for the topic,
    which is what turns the tree into a *budgeting* tree: the advisor allocates
    study time proportional to weight, not to chapter count. Nullable because
    «وزن‌گذاری نشده» must stay distinct from an honest «۰».

    ``CASCADE`` from the chapter — a topic of a chapter nobody seeded has no
    life of its own — while ``TopicProgress`` points here through ``SET_NULL``
    and keeps its mirrored title when the tree is re-seeded.
    """

    chapter = models.ForeignKey(
        SyllabusChapter,
        on_delete=models.CASCADE,
        related_name='syllabus_topics',
        verbose_name=_('فصل'),
    )
    title = models.CharField(max_length=200, verbose_name=_('عنوان مبحث'))
    order = models.PositiveSmallIntegerField(
        default=0,
        verbose_name=_('ترتیب'),
        help_text=_('جایگاه مبحث در فصل.'),
    )
    konkur_weight = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text=_('تعداد تقریبی سؤالات کنکور از این مبحث.'),
        verbose_name=_('وزن کنکوری'),
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('زمان ایجاد'))

    class Meta:
        ordering = ['chapter__order', 'order', 'title']
        constraints = [
            models.UniqueConstraint(
                fields=['chapter', 'title'],
                name='uniq_syllabus_topic_per_chapter',
                violation_error_message=_('این مبحث در این فصل از قبل ثبت شده است.'),
            ),
        ]
        verbose_name = _('مبحث درخت بودجه‌بندی')
        verbose_name_plural = _('مباحث درخت بودجه‌بندی')

    def __str__(self) -> str:
        return f'{self.title} ← {self.chapter}'


# ── Wave 5 (2026-08-31): the parent link ──────────────────────────────────────
#
# The parent is the first advisory reader who is neither the student nor the
# advisor, and the link row is how that read is *granted* — the counterpart of
# the student-side invite accept. An advisor names a phone; the row sits
# PENDING until whoever holds that phone proves ownership via OTP, at which
# point it flips ACTIVE and (only then) can read that one engagement's weekly
# digest. Tenancy-bearing like every advisory table: reads go through
# services/parent_links.py, pinned in test_import_boundaries.

PARENT_RELATION_CHOICES = [
    ('father', _('پدر')),
    ('mother', _('مادر')),
    ('guardian', _('سرپرست')),
]

# The AdvisoryAccessLog action the parent digest view records (D4: a read by
# someone outside the student/advisor pair is logged from the moment it exists).
PARENT_DIGEST_VIEW_ACTION = 'parent_digest_view'

# Two standing parents per student — father and mother is the overwhelming
# case; a guardian replaces either. A revoked link frees its slot.
MAX_PARENTS_PER_STUDENT = 2

PARENT_PHONE_REGEX = r'^09\d{9}$'
_validate_parent_phone = RegexValidator(
    PARENT_PHONE_REGEX,
    message=_('شمارهٔ والد باید ۰۹ + ۹ رقم باشد.'),
)


class ParentLink(models.Model):
    """One parent phone invited to read one engagement's weekly digest.

    Lifecycle::

        PENDING ──OTP verify──▶ ACTIVE ──revoke──▶ REVOKED   (kept for audit)

    ``parent`` is NULL until the phone's owner logs in with the OTP: the link
    is addressed to a *number*, not an account, exactly like an advisor invite
    — an advisor typing a wrong digit must never mint a user (B4). PROTECT on
    the resolved parent: a digest reader's account must not be deletable while
    links still point at it; revoke the link first.

    ``phone`` is stored canonical (``09`` + 9 digits, validated by the check
    below) because it is the join key of the OTP claim — every PENDING row
    addressed to the verified phone activates atomically on login.
    """

    class Status(models.TextChoices):
        PENDING = 'PENDING', _('در انتظار تأیید')
        ACTIVE = 'ACTIVE', _('فعال')
        REVOKED = 'REVOKED', _('لغوشده')

    engagement = models.ForeignKey(
        AdvisoryEngagement,
        on_delete=models.CASCADE,
        related_name='parent_links',
        verbose_name=_('همکاری'),
    )
    parent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='parent_links',
        verbose_name=_('والد'),
        help_text=_('تا ورود با کد یکبارمصرف خالی می‌ماند.'),
    )
    phone = models.CharField(
        max_length=11,
        db_index=True,
        validators=[_validate_parent_phone],
        verbose_name=_('شمارهٔ والد'),
        help_text=_('۰۹ + ۹ رقم؛ کلید اتصال هنگام ورود والد.'),
    )
    relation = models.CharField(
        max_length=8,
        choices=PARENT_RELATION_CHOICES,
        verbose_name=_('نسبت'),
    )
    status = models.CharField(
        max_length=8,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        verbose_name=_('وضعیت'),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='+',
        verbose_name=_('ایجادکننده'),
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('زمان ایجاد'))
    activated_at = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('تاریخ فعال‌سازی'),
        help_text=_('روزی که والد با کد یکبارمصرف وارد شد.'),
    )

    class Meta:
        ordering = ['created_at', 'id']
        constraints = [
            # One open/standing link per (engagement, phone): re-inviting the
            # same number while a PENDING/ACTIVE row exists is a duplicate,
            # while a REVOKED row must not block a fresh invite.
            models.UniqueConstraint(
                fields=['engagement', 'phone'],
                condition=models.Q(status__in=['PENDING', 'ACTIVE']),
                name='uniq_active_parent_link',
                violation_error_message=_('برای این شماره پیوند والد از قبل وجود دارد.'),
            ),
            models.CheckConstraint(
                condition=models.Q(phone__regex=PARENT_PHONE_REGEX),
                name='ck_parent_link_phone_shape',
                violation_error_message=_('شمارهٔ والد باید ۰۹ + ۹ رقم باشد.'),
            ),
        ]
        indexes = [
            # The OTP claim lookup: every PENDING row for one phone.
            models.Index(fields=['phone', 'status'], name='idx_parent_link_phone_status'),
            models.Index(fields=['engagement', 'status'], name='idx_parent_link_eng_status'),
        ]
        verbose_name = _('پیوند والد')
        verbose_name_plural = _('پیوندهای والدین')

    def __str__(self) -> str:
        return f'{self.relation} {self.phone} [{self.status}] ← #{self.engagement_id}'



