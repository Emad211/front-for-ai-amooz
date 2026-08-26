"""Serializers for the advisory API.

Wire shape is camelCase, matching ``organizations`` and ``classes`` — the
frontend consumes these directly with no key mapping layer.

Two rules hold for every serializer below, and both are deliberate:

* **A phone number is never returned in full**, to anyone, anywhere in advisory.
  Not even back to the advisor who typed it. It costs nothing (a masked number is
  still recognisable to the person who entered it) and it means a stolen session
  cannot be harvested for a contact list.
* **Engagement serializers are plain ``Serializer``, not ``ModelSerializer``**, so
  the exposed field set is an explicit allowlist that cannot grow when a column is
  added to the model. This repo has already shipped that exact leak once —
  ``TeacherStudentSerializer`` exposed ``inviteCode`` because a ModelSerializer
  picked it up. B5 forbids repeating it. It also keeps this file free of a
  tenancy-bearing model import, which the ``test_import_boundaries`` guard checks.
  The ``MAX_*``/``MOOD_*`` field bounds imported below are *not* such an import: a
  length ceiling says nothing about whose row it is, and validating against the
  same constant the column is declared with is what stops a serializer and a
  ``CheckConstraint`` from drifting into a 500.
"""

from __future__ import annotations

import datetime

from rest_framework import serializers

from apps.commons.phone_utils import is_valid_iran_mobile, normalize_phone

from .models import (
    MAX_LOG_MINUTES_PER_ITEM,
    MAX_LOG_NOTE_CHARS,
    MOOD_MAX,
    MOOD_MIN,
    Subject,
)
from .services.assessments import assessment_average
from .services.student_subjects import MAX_SUBJECTS_PER_STUDENT
from .services.study_plans import plan_adherence_percent
from .services.text import mask_phone


def _display_name(user) -> str:
    """A human label for a user, without leaking contact details.

    Falls back to ``username`` rather than to a generic «مشاور»: the student is
    being asked to grant a stranger read access to their study log, so a banner
    that cannot say *who* is asking is worse than useless — they would accept
    blind or reject a legitimate advisor.
    """
    if user is None:
        return ''
    full = ' '.join(filter(None, [user.first_name, user.last_name])).strip()
    return full or user.username


class SubjectSerializer(serializers.ModelSerializer):
    """Read-only projection of a catalog subject.

    ``normalized_name`` is deliberately absent: it is an internal duplicate key,
    not information the advisor needs, and exposing it would invite a client to
    start matching on it.
    """

    organizationId = serializers.IntegerField(
        source='organization_id', read_only=True, allow_null=True,
    )
    organizationName = serializers.CharField(
        source='organization.name', read_only=True, default=None,
    )
    isGlobal = serializers.BooleanField(source='is_global', read_only=True)
    isActive = serializers.BooleanField(source='is_active', read_only=True)
    # The raw codes for the client, plus ready Persian labels so no client
    # re-implements the choice maps. Both are identity axes now (see Subject):
    # ``grade=null`` is a dead/legacy row, ``major=null`` is a general subject
    # shared across every major of the grade.
    grade = serializers.CharField(read_only=True, allow_null=True)
    gradeLabel = serializers.SerializerMethodField()
    major = serializers.CharField(read_only=True, allow_null=True)
    majorLabel = serializers.SerializerMethodField()

    class Meta:
        model = Subject
        fields = [
            'id',
            'name',
            'organizationId',
            'organizationName',
            'isGlobal',
            'isActive',
            'grade',
            'gradeLabel',
            'major',
            'majorLabel',
        ]
        read_only_fields = fields

    def get_gradeLabel(self, obj) -> str | None:  # noqa: N802 — camelCase wire key
        return obj.get_grade_display() if obj.grade else None

    def get_majorLabel(self, obj) -> str | None:  # noqa: N802 — camelCase wire key
        return obj.get_major_display() if obj.major else None


class AdvisoryInviteCreateSerializer(serializers.Serializer):
    """The one input the invite endpoint takes: a phone number.

    Validation here checks the *shape of the string only* — never whether it
    belongs to anyone. That distinction is the whole of B2: rejecting «۰۹۱۲» with
    400 tells the caller about their own typing, whereas rejecting an unclaimed
    number would tell them about the platform's user table.
    """

    phone = serializers.CharField(max_length=20, write_only=True)

    def validate_phone(self, value: str) -> str:
        normalized = normalize_phone(value)
        if not is_valid_iran_mobile(normalized):
            raise serializers.ValidationError('شماره‌ی موبایل معتبر نیست (مثال: ۰۹۱۲۳۴۵۶۷۸۹).')
        return normalized


class AdvisorPendingInviteSerializer(serializers.Serializer):
    """The advisor's outbox — an invite with the invitee stripped out.

    This carries **no field about the person invited**: no name, no id, no avatar,
    only the masked number the advisor themselves typed. That is not politeness,
    it is the difference between two very different leaks. A row appears here only
    when the number belongs to a registered student, so the *existence* of the row
    already answers "is this number on the platform?" — a bounded, attributable,
    rate-capped signal we accept. Adding a name would upgrade that to the full
    phone→identity oracle B2 forbids. Do not add one; the student's name becomes
    visible the moment they accept, which is the correct trigger.
    """

    id = serializers.IntegerField(read_only=True)
    phoneMasked = serializers.SerializerMethodField()
    invitedAt = serializers.DateTimeField(source='invited_at', read_only=True)
    expiresAt = serializers.DateTimeField(
        source='invite_expires_at', read_only=True, allow_null=True,
    )
    isExpired = serializers.BooleanField(source='is_expired', read_only=True)

    def get_phoneMasked(self, obj) -> str:  # noqa: N802 — camelCase wire key
        return mask_phone(obj.invited_phone)


class AdvisorStudentSerializer(serializers.Serializer):
    """An accepted student, as their advisor sees them.

    ``id`` is the **engagement** id, and there is deliberately no ``studentId`` on
    the wire. Every advisory route from step 5 on is keyed by engagement, because
    the engagement *is* the tenancy check — a ``/students/<studentId>/`` URL would
    look equivalent while skipping it. Not publishing the student id is what stops
    that URL from being invented.
    """

    id = serializers.IntegerField(read_only=True)
    studentName = serializers.SerializerMethodField()
    phoneMasked = serializers.SerializerMethodField()
    mode = serializers.CharField(read_only=True)
    organizationName = serializers.CharField(
        source='organization.name', read_only=True, default=None,
    )
    startedOn = serializers.DateField(source='started_on', read_only=True, allow_null=True)
    status = serializers.CharField(read_only=True)

    def get_studentName(self, obj) -> str:  # noqa: N802 — camelCase wire key
        return _display_name(obj.student)

    def get_phoneMasked(self, obj) -> str:  # noqa: N802 — camelCase wire key
        # Masked even here, where the advisor typed the number themselves: an
        # org-mode student (step 9) never had their number typed by this advisor,
        # and one uniform rule cannot be got wrong when that case arrives.
        return mask_phone(obj.invited_phone or getattr(obj.student, 'phone', ''))


class StudentInviteSerializer(serializers.Serializer):
    """A pending invite as the *student* sees it — the accept-banner payload.

    The masked number is the student's own, and it is the point of the banner: it
    is the only way to notice an invite addressed to a number that used to be
    someone else's. ``advisorName`` is present here and absent from the advisor's
    outbox for symmetric reasons — each side is told who the *other* party is only
    when they have a reason to know.
    """

    id = serializers.IntegerField(read_only=True)
    advisorName = serializers.SerializerMethodField()
    invitedPhoneMasked = serializers.SerializerMethodField()
    mode = serializers.CharField(read_only=True)
    organizationName = serializers.CharField(
        source='organization.name', read_only=True, default=None,
    )
    invitedAt = serializers.DateTimeField(source='invited_at', read_only=True)
    expiresAt = serializers.DateTimeField(
        source='invite_expires_at', read_only=True, allow_null=True,
    )

    def get_advisorName(self, obj) -> str:  # noqa: N802 — camelCase wire key
        return _display_name(obj.advisor)

    def get_invitedPhoneMasked(self, obj) -> str:  # noqa: N802 — camelCase wire key
        return mask_phone(obj.invited_phone)


class StudentEngagementSerializer(serializers.Serializer):
    """The student's current advisor, if they have one."""

    id = serializers.IntegerField(read_only=True)
    advisorName = serializers.SerializerMethodField()
    mode = serializers.CharField(read_only=True)
    organizationName = serializers.CharField(
        source='organization.name', read_only=True, default=None,
    )
    startedOn = serializers.DateField(source='started_on', read_only=True, allow_null=True)
    status = serializers.CharField(read_only=True)

    def get_advisorName(self, obj) -> str:  # noqa: N802 — camelCase wire key
        return _display_name(obj.advisor)


class StudentSubjectSerializer(serializers.Serializer):
    """One selected subject, read off a ``StudentSubject`` row.

    A plain ``Serializer`` that reads attributes through the row's ``subject``
    relation, so this file never imports the tenancy-bearing ``StudentSubject``
    model (``test_import_boundaries``). It projects only the catalog facts a client
    renders — id, name, grade tag, global/private — never the engagement it hangs
    off or the ``is_active`` bookkeeping, both of which are internal.
    """

    subjectId = serializers.IntegerField(source='subject_id', read_only=True)
    name = serializers.CharField(source='subject.name', read_only=True)
    grade = serializers.CharField(source='subject.grade', read_only=True, allow_null=True)
    gradeLabel = serializers.SerializerMethodField()
    isGlobal = serializers.BooleanField(source='subject.is_global', read_only=True)
    # Restart step 3: the raw source code (or null = «not chosen»). The Persian
    # label is the frontend's job — it owns SUBJECT_SOURCE_LABELS for both the
    # picker and the student mirror, so there is exactly one label map.
    source = serializers.CharField(read_only=True, allow_null=True)

    def get_gradeLabel(self, obj) -> str | None:  # noqa: N802 — camelCase wire key
        subject = obj.subject
        return subject.get_grade_display() if subject.grade else None


class EngagementSubjectsWriteSerializer(serializers.Serializer):
    """The advisor's PUT body: the complete set of subject ids for a student.

    Shape only — assignability (does this advisor own this subject?) is the
    service's job, because that answer needs the advisor's org scope, which a
    serializer does not have. Here we only guarantee a clean list of positive ints:
    duplicates collapsed (ticking a box twice is not an error) and a ceiling that
    turns a scripted 10⁴-id payload into a 400 instead of ten thousand rows.
    ``allow_empty`` is intentional — an empty list is the "clear my selection" move.
    """

    subjectIds = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=True,
    )

    def validate_subjectIds(self, value):  # noqa: N802 — camelCase wire key
        deduped = list(dict.fromkeys(value))
        if len(deduped) > MAX_SUBJECTS_PER_STUDENT:
            raise serializers.ValidationError(
                f'حداکثر {MAX_SUBJECTS_PER_STUDENT} درس می‌توانید انتخاب کنید.'
            )
        return deduped


# ── S5: the daily study log ──────────────────────────────────────────────────

class DailyLogItemSerializer(serializers.Serializer):
    """One subject's minutes inside a day, read off a ``DailyLogItem`` row.

    ``subjectId`` is the **catalog** id, not the ``StudentSubject`` row id — the
    same vocabulary ``StudentSubjectSerializer`` publishes, so a client can join the
    day's items against the subject list it already has, and no tenancy-bearing row
    id ever reaches the wire.

    ``isSelected`` is the one field here that is not obvious, and dropping it would
    be a real bug. Items survive their subject being dropped from the student's list
    (an advisor changing the plan must not erase minutes already studied), so a day
    can legitimately contain a subject that is *not* in ``subjects``. A client that
    builds its rows only from the active list would then render a total that
    disagrees with ``totalMinutes``. This flag is how the form knows to show such a
    row as read-only history instead.
    """

    subjectId = serializers.IntegerField(
        source='student_subject.subject_id', read_only=True,
    )
    name = serializers.CharField(source='student_subject.subject.name', read_only=True)
    minutes = serializers.IntegerField(source='actual_minutes', read_only=True)
    isSelected = serializers.BooleanField(source='student_subject.is_active', read_only=True)


class DailyLogSerializer(serializers.Serializer):
    """One stored day.

    ``mood`` is nullable on purpose and the null is meaningful: «not recorded» is a
    different answer from «۱ / بد», and collapsing them would make the step-6 feed
    read a silent day as a miserable one. ``testPercent`` follows the same rule:
    ``null`` is «not recorded», distinct from an honest «۰».
    """

    date = serializers.DateField(source='log_date', read_only=True)
    mood = serializers.IntegerField(read_only=True, allow_null=True)
    note = serializers.CharField(read_only=True, allow_blank=True)
    # Restart plan step 1: the PDF-derived enrichment, additive camelCase keys.
    dayGoal = serializers.CharField(source='day_goal', read_only=True)
    motivationNote = serializers.CharField(source='motivation_note', read_only=True)
    testsTaken = serializers.IntegerField(source='tests_taken', read_only=True)
    testPercent = serializers.IntegerField(
        source='test_percent', read_only=True, allow_null=True,
    )
    items = DailyLogItemSerializer(many=True, read_only=True)
    totalMinutes = serializers.SerializerMethodField()
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)

    def get_totalMinutes(self, obj) -> int:  # noqa: N802 — camelCase wire key
        # Summed in Python over the already-prefetched items (``scope.student_logs``),
        # not with an aggregate: an ``.aggregate()`` here would fire one extra query
        # per day and defeat the prefetch on the step-6 feed.
        return sum(item.actual_minutes for item in obj.items.all())


class DailyLogItemWriteSerializer(serializers.Serializer):
    """One ``{subjectId, minutes}`` pair from the student's form.

    ``source='subject_id'`` is deliberate: the wire key stays camelCase while
    ``validated_data`` comes out in exactly the vocabulary ``services.daily_logs``
    documents, so the view hands the list straight to ``save_day`` with no re-keying
    step in between to get wrong.

    ``min_value=0`` — zero is not an error, it is how the form says «this subject, no
    minutes today»; the service drops those rather than storing a row the DB check
    would reject anyway. The ceiling is the same constant the column is declared
    with, so an over-long day is a 400 and never an ``IntegrityError`` 500.
    """

    subjectId = serializers.IntegerField(source='subject_id', min_value=1)
    minutes = serializers.IntegerField(min_value=0, max_value=MAX_LOG_MINUTES_PER_ITEM)


class DailyLogWriteSerializer(serializers.Serializer):
    """The student's PUT body: one whole day.

    Everything about the day is here, because the endpoint is a set-replace. That is
    also why ``items`` is **required** while ``mood``/``note`` are not: an absent
    ``items`` would silently wipe the day's minutes, so the client has to say
    ``[]`` and mean it, whereas an absent mood clearing the mood is harmless and
    matches «I did not answer that question».

    The four enrichment keys (``dayGoal``/``motivationNote``/``testsTaken``/
    ``testPercent``) are the one deliberate exception: an absent key leaves the
    stored column untouched, so a client written before they existed cannot erase
    data it never sent. Sending a key — even as ``null``/``''`` — overwrites.

    Shape only. Whether the date is inside the engagement's window and whether each
    subject is on this student's list are the service's job — both need the
    engagement, which a serializer does not have.
    """

    date = serializers.DateField(source='log_date')
    mood = serializers.IntegerField(
        required=False, allow_null=True, min_value=MOOD_MIN, max_value=MOOD_MAX,
    )
    note = serializers.CharField(
        required=False, allow_blank=True, max_length=MAX_LOG_NOTE_CHARS,
    )
    # Restart plan step 1: optional enrichment. An ABSENT key leaves the stored
    # column untouched (legacy payloads must not wipe what they don't know
    # about); a PRESENT key overwrites wholesale. Range messages are Persian
    # here rather than field-level ``min_value``/``max_value`` so the 400 the
    # student sees is actionable in their own language.
    dayGoal = serializers.CharField(
        source='day_goal', required=False, allow_blank=True, max_length=200,
    )
    motivationNote = serializers.CharField(
        source='motivation_note', required=False, allow_blank=True, max_length=200,
    )
    testsTaken = serializers.IntegerField(source='tests_taken', required=False)
    testPercent = serializers.IntegerField(
        source='test_percent', required=False, allow_null=True,
    )
    items = DailyLogItemWriteSerializer(many=True)

    def validate_testsTaken(self, value):  # noqa: N802 — camelCase wire key
        if value < 0:
            raise serializers.ValidationError('تعداد تست نمی‌تواند عددی منفی باشد.')
        return value

    def validate_testPercent(self, value):  # noqa: N802 — camelCase wire key
        if value is not None and not (0 <= value <= 100):
            raise serializers.ValidationError('درصد آزمون باید عددی بین ۰ تا ۱۰۰ باشد.')
        return value

    def validate_items(self, value):
        """Reject a repeated subject, and cap the list length.

        Unlike ``subjectIds`` above — where ticking a box twice is harmless and gets
        collapsed — two entries for one subject carry two different minute counts and
        there is no honest way to pick one. The service's dict build is last-wins as a
        backstop; this is where it becomes a 400 the student can act on.

        The ceiling is the selection ceiling: you cannot report minutes for more
        subjects than you are allowed to have, so a scripted 10⁴-item payload is a
        400 instead of 10⁴ upserts inside one transaction.
        """
        if len(value) > MAX_SUBJECTS_PER_STUDENT:
            raise serializers.ValidationError(
                f'حداکثر {MAX_SUBJECTS_PER_STUDENT} درس در یک روز قابل ثبت است.'
            )
        subject_ids = [item['subject_id'] for item in value]
        if len(set(subject_ids)) != len(subject_ids):
            raise serializers.ValidationError('برای هر درس فقط یک ردیف بفرستید.')
        return value


# ── S6/S7 (§14): the study feed and the study planner ────────────────────────

class StudyPlanItemOutSerializer(serializers.Serializer):
    """One planned row, read off a ``StudyPlanItem``.

    ``subjectId`` is the catalog id — the same vocabulary every other advisory
    serializer publishes. ``date`` is computed (``start_date + day_offset``)
    rather than stored: the plan stays movable, shifting its start without
    rewriting a single item row.
    """

    dayOffset = serializers.IntegerField(source='day_offset', read_only=True)
    date = serializers.SerializerMethodField()
    subjectId = serializers.IntegerField(
        source='student_subject.subject_id', read_only=True,
    )
    name = serializers.CharField(source='student_subject.subject.name', read_only=True)
    plannedMinutes = serializers.IntegerField(
        source='planned_minutes', read_only=True,
    )
    # Restart step 4: per-row enrichment, additive. ``testMinutes`` is null when
    # the advisor set no test budget — distinct from an honest 0.
    topic = serializers.CharField(read_only=True)
    unitLabel = serializers.CharField(source='unit_label', read_only=True)
    testMinutes = serializers.IntegerField(
        source='test_minutes', read_only=True, allow_null=True,
    )
    masteryColor = serializers.CharField(
        source='mastery_color', read_only=True, allow_null=True,
    )

    def get_date(self, obj):  # noqa: N802 — camelCase wire key
        return obj.plan.start_date + datetime.timedelta(days=obj.day_offset)


class StudyPlanOutSerializer(serializers.Serializer):
    """The one plan shape (``PlanOut``) every plan answer reuses.

    PUT draft, publish and unpublish all respond with this same serializer off
    the **stored** row, so a successful write can never paint a state a refresh
    would contradict — the same rule ``_study_log_payload`` enforces for S5.
    ``endDate`` is inclusive: ``start + duration - 1``, matching the overlap
    arithmetic the service publishes.
    """

    id = serializers.IntegerField(read_only=True)
    startDate = serializers.DateField(source='start_date', read_only=True)
    endDate = serializers.SerializerMethodField()
    durationDays = serializers.IntegerField(source='duration_days', read_only=True)
    status = serializers.CharField(read_only=True)
    percent = serializers.SerializerMethodField()
    items = StudyPlanItemOutSerializer(many=True, read_only=True)
    # Restart step 4: the per-day note blocks, additive. Always a dict (the
    # column defaults to {}), keyed '0'..'6' as strings.
    dayNotes = serializers.JSONField(source='day_notes', read_only=True)

    def get_endDate(self, obj):  # noqa: N802 — camelCase wire key
        return obj.end_date

    def get_percent(self, obj) -> int | None:  # noqa: N802 — camelCase wire key
        """Adherence percent; ``None`` unless the plan is PUBLISHED.

        A draft promises nothing yet, so it carries no measurement rather than
        a misleading ``0``. The status test reads the instance's nested enum —
        not a model import — for the same import-boundary reason views do.
        """
        if obj.status != obj.Status.PUBLISHED:
            return None
        return plan_adherence_percent(obj)


class StudyPlanDraftItemWriteSerializer(serializers.Serializer):
    """One ``{dayOffset, subjectId, plannedMinutes}`` row of the draft body.

    Shape only, deliberately without bounds: the exact Persian messages and
    their *order* (offset → subject → minutes → duplicates) are the service's
    contract (§14.3), and a serializer-level bound would answer first with a
    generic DRF message instead.

    Restart step 4 adds four optional enrichment keys on the same terms — the
    service owns their bounds and messages; absent keys store column defaults.
    """

    dayOffset = serializers.IntegerField(source='day_offset')
    subjectId = serializers.IntegerField(source='subject_id', min_value=1)
    plannedMinutes = serializers.IntegerField(source='planned_minutes')
    topic = serializers.CharField(required=False, allow_blank=True)
    unitLabel = serializers.CharField(
        source='unit_label', required=False, allow_blank=True,
    )
    testMinutes = serializers.IntegerField(
        source='test_minutes', required=False, allow_null=True,
    )
    masteryColor = serializers.CharField(
        source='mastery_color', required=False, allow_null=True, allow_blank=True,
    )


class StudyPlanDraftWriteSerializer(serializers.Serializer):
    """The advisor's PUT body: the whole draft slot, set-replace semantics.

    Everything about the draft is here because the endpoint upserts the single
    DRAFT row wholesale — an omitted field means «cleared», never «unchanged».
    Whether the start predates the engagement, whether the length fits 1..90 and
    whether each row is legal are the service's job; this only guarantees typed,
    parseable input.

    The one deliberate exception is ``dayNotes`` (restart step 4): an ABSENT key
    leaves the stored notes untouched (legacy-payload safety, same rule as the
    daily-log enrichment), while a PRESENT key replaces them wholesale. Its shape
    is validated in the service, which owns the exact Persian message.
    """

    startDate = serializers.DateField(source='start_date')
    durationDays = serializers.IntegerField(source='duration_days')
    items = StudyPlanDraftItemWriteSerializer(many=True)
    dayNotes = serializers.JSONField(source='day_notes', required=False)


class FeedDayItemSerializer(serializers.Serializer):
    """One subject's minutes inside a feed day — no ``isSelected`` here.

    Unlike the S5 form payload, the feed is a read-only report: it renders what
    was recorded, selected or not, and has no editable rows to flag.
    """

    subjectId = serializers.IntegerField(
        source='student_subject.subject_id', read_only=True,
    )
    name = serializers.CharField(source='student_subject.subject.name', read_only=True)
    minutes = serializers.IntegerField(source='actual_minutes', read_only=True)


class FeedDaySerializer(serializers.Serializer):
    """One logged day inside the advisor's study feed."""

    date = serializers.DateField(source='log_date', read_only=True)
    totalMinutes = serializers.SerializerMethodField()
    mood = serializers.IntegerField(read_only=True, allow_null=True)
    note = serializers.CharField(read_only=True, allow_blank=True)
    # Restart plan step 1: the feed renders the «تست»/«درصد» chips off these.
    testsTaken = serializers.IntegerField(source='tests_taken', read_only=True)
    testPercent = serializers.IntegerField(
        source='test_percent', read_only=True, allow_null=True,
    )
    items = FeedDayItemSerializer(many=True, read_only=True)

    def get_totalMinutes(self, obj) -> int:  # noqa: N802 — camelCase wire key
        # Summed over the prefetched items (``scope.advisor_feed_logs``), not
        # with an aggregate — same reasoning as ``DailyLogSerializer``.
        return sum(item.actual_minutes for item in obj.items.all())


# ── Restart wave 3: intake (step 2), weekly assessment (step 7), call log ────
#
# Same split as the rest of the file: read serializers project stored rows,
# write serializers are shape-only — the exact Persian validation messages and
# their order are the services' contract (services/intake.py, services/
# assessments.py, services/calls.py), so a serializer-level bound can never
# answer first with a generic DRF message where the wire pins a Persian one.


def _hhmm(value):
    """A ``datetime.time`` as ``HH:MM``, or ``None`` — the intake wire format."""
    return value.strftime('%H:%M') if value is not None else None


class IntakeClassOutSerializer(serializers.Serializer):
    """One class row of the intake payload, read off an ``AdvisoryIntakeClass``."""

    name = serializers.CharField(read_only=True)
    teacher = serializers.CharField(read_only=True)
    weekday = serializers.IntegerField(read_only=True)
    startTime = serializers.SerializerMethodField()
    endTime = serializers.SerializerMethodField()
    order = serializers.IntegerField(read_only=True)

    def get_startTime(self, obj):  # noqa: N802 — camelCase wire key
        return _hhmm(obj.start_time)

    def get_endTime(self, obj):  # noqa: N802 — camelCase wire key
        return _hhmm(obj.end_time)


class IntakePayloadSerializer(serializers.Serializer):
    """The whole intake form as one object — GET response and PUT response alike.

    Both verbs answer with this off the **stored** profile, so a successful save
    can never paint a state a refresh would contradict. ``lastGpa``/``freeDayMinutes``
    are ``null`` when never recorded, which is distinct from an honest ``0``.
    """

    school = serializers.CharField(read_only=True)
    city = serializers.CharField(read_only=True)
    lastGpa = serializers.DecimalField(
        source='last_gpa', read_only=True, allow_null=True,
        max_digits=4, decimal_places=2, coerce_to_string=False,
    )
    targetMajor = serializers.CharField(source='target_major', read_only=True)
    targetUniversity = serializers.CharField(source='target_university', read_only=True)
    mockExamInstitute = serializers.CharField(source='mock_exam_institute', read_only=True)
    freeDayMinutes = serializers.IntegerField(
        source='free_day_minutes', read_only=True, allow_null=True,
    )
    classes = IntakeClassOutSerializer(many=True, source='classes.all')


class IntakeClassWriteSerializer(serializers.Serializer):
    """One ``{name, teacher, weekday, startTime, endTime, order}`` row of the body.

    Shape only: the weekday band, the end>start rule and the row cap are the
    service's pinned Persian messages. Times accept ``HH:MM`` or null.
    """

    name = serializers.CharField(max_length=120)
    teacher = serializers.CharField(required=False, allow_blank=True, max_length=120)
    weekday = serializers.IntegerField()
    startTime = serializers.TimeField(source='start_time', required=False, allow_null=True)
    endTime = serializers.TimeField(source='end_time', required=False, allow_null=True)
    order = serializers.IntegerField(required=False)


class IntakeWriteSerializer(serializers.Serializer):
    """The intake PUT body: the complete form, set-replace semantics.

    Every scalar is optional on the wire because absence means «cleared» — the
    endpoint replaces the form wholesale, like every advisory PUT. ``classes``
    is required so clearing the timetable is always an explicit ``[]``.
    """

    school = serializers.CharField(required=False, allow_blank=True, max_length=120)
    city = serializers.CharField(required=False, allow_blank=True, max_length=60)
    # Loose digits on purpose: any plausible GPA parses here, and the 0..20
    # band itself stays the service's pinned Persian message.
    lastGpa = serializers.DecimalField(
        source='last_gpa', required=False, allow_null=True,
        max_digits=5, decimal_places=2,
    )
    targetMajor = serializers.CharField(
        source='target_major', required=False, allow_blank=True, max_length=120,
    )
    targetUniversity = serializers.CharField(
        source='target_university', required=False, allow_blank=True, max_length=120,
    )
    mockExamInstitute = serializers.CharField(
        source='mock_exam_institute', required=False, allow_blank=True, max_length=120,
    )
    freeDayMinutes = serializers.IntegerField(
        source='free_day_minutes', required=False, allow_null=True,
    )
    classes = IntakeClassWriteSerializer(many=True)


class WeeklyAssessmentItemSerializer(serializers.Serializer):
    """One week's assessment in the wire shape shared by list and upsert."""

    weekStart = serializers.DateField(source='week_start', read_only=True)
    scores = serializers.JSONField(read_only=True)
    advisorSummary = serializers.CharField(source='advisor_summary', read_only=True)
    average = serializers.SerializerMethodField()

    def get_average(self, obj) -> float:  # noqa: N802 — camelCase wire key
        return assessment_average(obj.scores)


class WeeklyAssessmentWriteSerializer(serializers.Serializer):
    """The assessment PUT body: all 15 scores plus the optional text summary.

    ``scores`` rides through as raw JSON because every failure shape (missing
    criterion, unknown code, non-int, out of 1..5) has its own pinned Persian
    message owned by ``services.assessments.validate_scores``.
    """

    scores = serializers.JSONField()
    advisorSummary = serializers.CharField(
        source='advisor_summary', required=False, allow_blank=True,
    )


class CallLogItemSerializer(serializers.Serializer):
    """One week of the call checklist — works off dicts and rows alike.

    The service builds plain dicts (stored *and* virtual weeks share one shape),
    and DRF's attribute lookup falls back to mapping keys, so this single
    serializer covers both without a second code path.
    """

    weekStart = serializers.DateField(read_only=True)
    done = serializers.BooleanField(read_only=True)
    callDate = serializers.DateField(read_only=True, allow_null=True)
    topic = serializers.CharField(read_only=True)
    note = serializers.CharField(read_only=True, allow_blank=True)


class CallLogWriteSerializer(serializers.Serializer):
    """The call-log PUT body: ``done`` required; the rest keep-when-absent.

    Absent ``callDate``/``topic``/``note`` keys mean «unchanged» (upsert
    semantics — unlike the intake form, these fields accumulate). Sending a key
    overwrites it, including back to null/empty.
    """

    done = serializers.BooleanField()
    callDate = serializers.DateField(source='call_date', required=False, allow_null=True)
    topic = serializers.CharField(required=False, allow_blank=True, max_length=200)
    note = serializers.CharField(required=False, allow_blank=True)


# ── Restart wave 4: exam scores (step 5) and exam analyses (step 6) ──────────
#
# Same split as the rest of the file: read serializers project stored rows,
# write serializers are shape-only — every domain bound and its pinned Persian
# message is services/exam_records.py's contract, so a serializer-level rule
# can never answer first where the wire pins a specific message.


class ExamScoreItemSerializer(serializers.Serializer):
    """One row of the «نمرات کسب‌شده» table, read off a ``StudyExamScore``.

    ``subjectId``/``subjectName`` are null when the row carries no catalog
    link — most rows name their exam freely in ``title``.
    """

    id = serializers.IntegerField(read_only=True)
    title = serializers.CharField(read_only=True)
    subjectId = serializers.IntegerField(
        source='subject_id', read_only=True, allow_null=True,
    )
    subjectName = serializers.CharField(
        source='subject.name', read_only=True, default=None,
    )
    examKind = serializers.CharField(source='exam_kind', read_only=True)
    examDate = serializers.DateField(source='exam_date', read_only=True)
    scorePercent = serializers.DecimalField(
        source='score_percent', read_only=True,
        max_digits=5, decimal_places=2, coerce_to_string=False,
    )
    tara = serializers.IntegerField(read_only=True, allow_null=True)
    advisorRating = serializers.CharField(
        source='advisor_rating', read_only=True, allow_null=True,
    )
    advisorNote = serializers.CharField(source='advisor_note', read_only=True)


class ExamScoreWriteSerializer(serializers.Serializer):
    """The POST body: one new score row.

    Shape only. The four required keys are what a row cannot exist without;
    everything else defaults to null/empty. Loose digits on ``scorePercent``
    on purpose — any plausible number parses here so an out-of-range value
    reaches the service's pinned «درصد باید بین ۰ تا ۱۰۰ باشد.» instead of a
    generic DRF digit-count error.
    """

    title = serializers.CharField(max_length=120)
    subjectId = serializers.IntegerField(
        source='subject_id', required=False, allow_null=True,
    )
    examKind = serializers.CharField(source='exam_kind')
    examDate = serializers.DateField(source='exam_date')
    scorePercent = serializers.DecimalField(
        source='score_percent', max_digits=10, decimal_places=2,
    )
    tara = serializers.IntegerField(required=False, allow_null=True)
    advisorRating = serializers.CharField(
        source='advisor_rating', required=False, allow_null=True, allow_blank=True,
    )
    advisorNote = serializers.CharField(
        source='advisor_note', required=False, allow_blank=True,
    )


class ExamScorePatchSerializer(ExamScoreWriteSerializer):
    """The PATCH body: every key optional; only provided keys change."""

    title = serializers.CharField(required=False, max_length=120)
    examKind = serializers.CharField(source='exam_kind', required=False)
    examDate = serializers.DateField(source='exam_date', required=False)
    scorePercent = serializers.DecimalField(
        source='score_percent', required=False, max_digits=10, decimal_places=2,
    )


class ExamAnalysisRowItemSerializer(serializers.Serializer):
    """One subject row of a stored analysis."""

    subjectName = serializers.CharField(source='subject_name', read_only=True)
    wrongCount = serializers.IntegerField(source='wrong_count', read_only=True)
    skippedCount = serializers.IntegerField(source='skipped_count', read_only=True)
    doubtfulTotal = serializers.IntegerField(
        source='doubtful_total', read_only=True,
    )
    doubtfulWrong = serializers.IntegerField(
        source='doubtful_wrong', read_only=True,
    )
    doubtfulSkipped = serializers.IntegerField(
        source='doubtful_skipped', read_only=True,
    )
    doubtfulCorrect = serializers.IntegerField(
        source='doubtful_correct', read_only=True,
    )
    causeNote = serializers.CharField(source='cause_note', read_only=True)


class ExamAnalysisNoteItemSerializer(serializers.Serializer):
    """One per-question note of a stored analysis."""

    questionNumber = serializers.IntegerField(
        source='question_number', read_only=True,
    )
    subjectName = serializers.CharField(source='subject_name', read_only=True)
    note = serializers.CharField(read_only=True)


class ExamAnalysisItemSerializer(serializers.Serializer):
    """One analysis in the wire shape shared by list, detail and mirror.

    Every metric is ``null`` when never recorded — distinct from an honest
    ``0``. ``rows`` keeps insertion order; ``notes`` come ordered by question
    number.
    """

    id = serializers.IntegerField(read_only=True)
    examNumber = serializers.IntegerField(
        source='exam_number', read_only=True, allow_null=True,
    )
    examDate = serializers.DateField(source='exam_date', read_only=True, allow_null=True)
    gradeBand = serializers.CharField(
        source='grade_band', read_only=True, allow_null=True,
    )
    totalTara = serializers.IntegerField(
        source='total_tara', read_only=True, allow_null=True,
    )
    nationalRank = serializers.IntegerField(
        source='national_rank', read_only=True, allow_null=True,
    )
    regionRank = serializers.IntegerField(
        source='region_rank', read_only=True, allow_null=True,
    )
    cityRank = serializers.IntegerField(
        source='city_rank', read_only=True, allow_null=True,
    )
    highestPercent = serializers.DecimalField(
        source='highest_percent', read_only=True,
        max_digits=5, decimal_places=2, coerce_to_string=False, allow_null=True,
    )
    lowestPercent = serializers.DecimalField(
        source='lowest_percent', read_only=True,
        max_digits=5, decimal_places=2, coerce_to_string=False, allow_null=True,
    )
    taraDelta = serializers.IntegerField(
        source='tara_delta', read_only=True, allow_null=True,
    )
    advisorReport = serializers.CharField(source='advisor_report', read_only=True)
    rows = ExamAnalysisRowItemSerializer(many=True, read_only=True)
    notes = ExamAnalysisNoteItemSerializer(many=True, read_only=True)


class ExamAnalysisRowWriteSerializer(serializers.Serializer):
    """One subject row of the create/PUT body. Shape only — the count bounds,
    the doubtful sub-counter rule and their pinned Persian messages are the
    service's contract."""

    subjectName = serializers.CharField(source='subject_name')
    wrongCount = serializers.IntegerField(
        source='wrong_count', required=False,
    )
    skippedCount = serializers.IntegerField(
        source='skipped_count', required=False,
    )
    doubtfulTotal = serializers.IntegerField(
        source='doubtful_total', required=False,
    )
    doubtfulWrong = serializers.IntegerField(
        source='doubtful_wrong', required=False,
    )
    doubtfulSkipped = serializers.IntegerField(
        source='doubtful_skipped', required=False,
    )
    doubtfulCorrect = serializers.IntegerField(
        source='doubtful_correct', required=False,
    )
    causeNote = serializers.CharField(
        source='cause_note', required=False, allow_blank=True, max_length=300,
    )


class ExamAnalysisNoteWriteSerializer(serializers.Serializer):
    """One per-question note of the create/PUT body. Shape only."""

    questionNumber = serializers.IntegerField(source='question_number')
    subjectName = serializers.CharField(source='subject_name')
    note = serializers.CharField(required=False, allow_blank=True)


class ExamAnalysisWriteSerializer(serializers.Serializer):
    """The POST/PUT body: the whole analysis document.

    ``rows`` and ``notes`` are required so clearing them is always an explicit
    ``[]`` — same rule as the intake form's ``classes``. Loose digits on the
    percent fields on purpose: any plausible number parses here so an
    out-of-range value reaches the service's pinned Persian message instead of
    a generic DRF digit-count error.
    """

    examNumber = serializers.IntegerField(
        source='exam_number', required=False, allow_null=True,
    )
    examDate = serializers.DateField(
        source='exam_date', required=False, allow_null=True,
    )
    gradeBand = serializers.CharField(
        source='grade_band', required=False, allow_null=True, allow_blank=True,
    )
    totalTara = serializers.IntegerField(
        source='total_tara', required=False, allow_null=True,
    )
    nationalRank = serializers.IntegerField(
        source='national_rank', required=False, allow_null=True,
    )
    regionRank = serializers.IntegerField(
        source='region_rank', required=False, allow_null=True,
    )
    cityRank = serializers.IntegerField(
        source='city_rank', required=False, allow_null=True,
    )
    highestPercent = serializers.DecimalField(
        source='highest_percent', required=False, allow_null=True,
        max_digits=10, decimal_places=2,
    )
    lowestPercent = serializers.DecimalField(
        source='lowest_percent', required=False, allow_null=True,
        max_digits=10, decimal_places=2,
    )
    taraDelta = serializers.IntegerField(
        source='tara_delta', required=False, allow_null=True,
    )
    advisorReport = serializers.CharField(
        source='advisor_report', required=False, allow_blank=True,
    )
    rows = ExamAnalysisRowWriteSerializer(many=True)
    notes = ExamAnalysisNoteWriteSerializer(many=True)


# ── Restart wave 5: monthly outlook + strategies (step 8) ────────────────────
#
# Same split as the rest of the file: read serializers project stored rows,
# write serializers are shape-only — every domain bound and its pinned Persian
# message is services/monthly.py's contract, so a serializer-level rule can
# never answer first where the wire pins a specific message.


class MonthlyOutlookEntryItemSerializer(serializers.Serializer):
    """One day's line of a stored outlook, read off a ``MonthlyOutlookEntry``."""

    date = serializers.DateField(read_only=True)
    event = serializers.CharField(read_only=True)
    academicNote = serializers.CharField(source='academic_note', read_only=True)
    tasks = serializers.CharField(read_only=True)


class MonthlyStrategyItemSerializer(serializers.Serializer):
    """One strategy slot of a stored outlook, read off a ``MonthlyStrategy``."""

    position = serializers.IntegerField(read_only=True)
    title = serializers.CharField(read_only=True)
    executor = serializers.CharField(read_only=True)
    body = serializers.CharField(read_only=True)


class MonthlyOutlookPayloadSerializer(serializers.Serializer):
    """The whole month as one object — GET response and PUT response alike.

    Both verbs answer with this off the **stored** outlook, so a successful
    save can never paint a state a refresh would contradict. ``monthStart``
    echoes the opaque Gregorian key (ق۵), not an interpreted calendar month.
    """

    monthStart = serializers.DateField(source='month_start', read_only=True)
    entries = MonthlyOutlookEntryItemSerializer(many=True, source='entries.all')
    strategies = MonthlyStrategyItemSerializer(many=True, source='strategies.all')


class MonthlyOutlookEntryWriteSerializer(serializers.Serializer):
    """One ``{date, event, academicNote, tasks}`` row of the PUT body.

    Shape only: no month-membership rule exists anywhere (boundary calendars
    are legal, ق۵); length ceilings and the per-day duplicate rule are the
    service's pinned messages.
    """

    date = serializers.DateField()
    event = serializers.CharField(required=False, allow_blank=True, max_length=120)
    academicNote = serializers.CharField(
        source='academic_note', required=False, allow_blank=True, max_length=200,
    )
    tasks = serializers.CharField(required=False, allow_blank=True)


class MonthlyStrategyWriteSerializer(serializers.Serializer):
    """One ``{position, title, executor, body}`` slot of the PUT body.

    Shape only — the 1..10 band, the executor codes and the duplicate-position
    rule each have their own pinned Persian message owned by
    ``services.monthly``; loose typing here lets those answers win.
    """

    position = serializers.IntegerField()
    title = serializers.CharField(required=False, allow_blank=True, max_length=120)
    executor = serializers.CharField()
    body = serializers.CharField(required=False, allow_blank=True)


class MonthlyOutlookWriteSerializer(serializers.Serializer):
    """The advisor's PUT body: the whole month, set-replace semantics.

    Both lists are required so clearing them is always an explicit ``[]`` —
    same rule as the intake form's ``classes``.
    """

    entries = MonthlyOutlookEntryWriteSerializer(many=True)
    strategies = MonthlyStrategyWriteSerializer(many=True)


# ── Restart wave 5: the 7-day challenge (step 9) ─────────────────────────────
#
# Same split as the rest of the file: read serializers project stored rows,
# write serializers are shape-only — every domain bound and its pinned Persian
# message is services/challenges.py's contract. The days body rides through as
# raw JSON on purpose: in student mode the door must see keys a nested
# serializer would silently drop, because "any field beyond goal/summary" is
# itself the pinned error.


class ChallengeDayItemSerializer(serializers.Serializer):
    """One day of a stored challenge, read off a ``StudyChallengeDay``."""

    dayNumber = serializers.IntegerField(source='day_number', read_only=True)
    goal = serializers.CharField(read_only=True)
    summary = serializers.CharField(read_only=True)


class ChallengeItemSerializer(serializers.Serializer):
    """One challenge in the wire shape shared by list, detail and mirror.

    ``endDate`` is the server-computed ``startDate + 6 days`` — it is echoed
    off the stored row so a client can never paint an end the server disagrees
    with.
    """

    id = serializers.IntegerField(read_only=True)
    title = serializers.CharField(read_only=True)
    goalText = serializers.CharField(source='goal_text', read_only=True)
    dailyRoutine = serializers.CharField(source='daily_routine', read_only=True)
    executionNote = serializers.CharField(source='execution_note', read_only=True)
    observer = serializers.CharField(read_only=True)
    problemTarget = serializers.CharField(source='problem_target', read_only=True)
    startDate = serializers.DateField(source='start_date', read_only=True)
    endDate = serializers.DateField(source='end_date', read_only=True)
    status = serializers.CharField(read_only=True)
    days = ChallengeDayItemSerializer(many=True, source='days.all')


class ChallengeCreateSerializer(serializers.Serializer):
    """The POST body: one new challenge's frame.

    Shape only. ``endDate`` is declared for wire compatibility and then
    deliberately ignored — the server derives it from ``startDate``, so a
    client-sent value can never bend the seven-day horizon.
    """

    title = serializers.CharField(required=False, allow_blank=True, max_length=120)
    goalText = serializers.CharField(
        source='goal_text', required=False, allow_blank=True,
    )
    dailyRoutine = serializers.CharField(
        source='daily_routine', required=False, allow_blank=True, max_length=200,
    )
    executionNote = serializers.CharField(
        source='execution_note', required=False, allow_blank=True, max_length=200,
    )
    observer = serializers.CharField(required=False, allow_blank=True, max_length=120)
    problemTarget = serializers.CharField(
        source='problem_target', required=False, allow_blank=True,
    )
    startDate = serializers.DateField(source='start_date')
    endDate = serializers.DateField(
        source='end_date', required=False, allow_null=True,
    )


class ChallengePatchSerializer(ChallengeCreateSerializer):
    """The PATCH body: every key optional; only provided keys change.

    A present ``startDate`` re-derives ``endDate`` server-side; a present
    ``status`` must follow the one-way ACTIVE → DONE/CANCELLED machine (the
    409 for anything else is the service's pinned message).
    """

    title = serializers.CharField(required=False, allow_blank=True, max_length=120)
    startDate = serializers.DateField(source='start_date', required=False)
    status = serializers.CharField(required=False)


class ChallengeDaysWriteSerializer(serializers.Serializer):
    """The days PUT body envelope: ``days`` is a list of raw row objects.

    Deliberately untyped children: the service validates each row itself so
    the student-mode rule («any field beyond goal/summary ⇒ pinned 400») can
    fire before DRF would silently discard the offending key.
    """

    days = serializers.ListField(child=serializers.JSONField())
