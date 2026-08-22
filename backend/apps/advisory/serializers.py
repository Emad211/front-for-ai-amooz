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

"""

from __future__ import annotations

from rest_framework import serializers

from apps.commons.phone_utils import is_valid_iran_mobile, normalize_phone

from .models import Subject
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
