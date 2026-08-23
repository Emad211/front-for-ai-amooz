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
from .services.student_subjects import MAX_SUBJECTS_PER_STUDENT
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
    read a silent day as a miserable one.
    """

    date = serializers.DateField(source='log_date', read_only=True)
    mood = serializers.IntegerField(read_only=True, allow_null=True)
    note = serializers.CharField(read_only=True, allow_blank=True)
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
    items = DailyLogItemWriteSerializer(many=True)

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
    items = StudyPlanItemOutSerializer(many=True, read_only=True)

    def get_endDate(self, obj):  # noqa: N802 — camelCase wire key
        return obj.end_date


class StudyPlanDraftItemWriteSerializer(serializers.Serializer):
    """One ``{dayOffset, subjectId, plannedMinutes}`` row of the draft body.

    Shape only, deliberately without bounds: the exact Persian messages and
    their *order* (offset → subject → minutes → duplicates) are the service's
    contract (§14.3), and a serializer-level bound would answer first with a
    generic DRF message instead.
    """

    dayOffset = serializers.IntegerField(source='day_offset')
    subjectId = serializers.IntegerField(source='subject_id', min_value=1)
    plannedMinutes = serializers.IntegerField(source='planned_minutes')


class StudyPlanDraftWriteSerializer(serializers.Serializer):
    """The advisor's PUT body: the whole draft slot, set-replace semantics.

    Everything about the draft is here because the endpoint upserts the single
    DRAFT row wholesale — an omitted field means «cleared», never «unchanged».
    Whether the start predates the engagement, whether the length fits 1..90 and
    whether each row is legal are the service's job; this only guarantees typed,
    parseable input.
    """

    startDate = serializers.DateField(source='start_date')
    durationDays = serializers.IntegerField(source='duration_days')
    items = StudyPlanDraftItemWriteSerializer(many=True)


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
    items = FeedDayItemSerializer(many=True, read_only=True)

    def get_totalMinutes(self, obj) -> int:  # noqa: N802 — camelCase wire key
        # Summed over the prefetched items (``scope.advisor_feed_logs``), not
        # with an aggregate — same reasoning as ``DailyLogSerializer``.
        return sum(item.actual_minutes for item in obj.items.all())
