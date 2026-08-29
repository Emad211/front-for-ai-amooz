"""Django admin for the advisory app.

The ``Subject`` catalog has no write API in the MVP on purpose: it is curated
slowly by a platform admin, not authored by advisors. Django admin *is* the
write surface, which means it is reachable only on the backend host — the
frontend rewrite does not proxy ``/admin/`` (see E3 in the spec).

``AdvisoryEngagement`` is registered read-mostly, for a different reason: it is
the support tool for "my advisor disappeared" tickets, and it is the only place an
operator can end an engagement. It is deliberately *not* creatable here — an
engagement created by an admin would have no ``terms_accepted_at``, i.e. a student
who never agreed to be watched.

``DailyLog`` goes one step further and is registered **fully read-only**: it is the
student's own statement about their own day, so there is no operator edit that would
not be putting words in their mouth.
"""

from django.contrib import admin

from .models import (
    AdvisoryAccessLog,
    AdvisoryEngagement,
    DailyLog,
    DailyLogItem,
    StudentSubject,
    Subject,
)


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'grade', 'major', 'scope_label', 'is_active', 'created_at')
    list_filter = ('is_active', 'grade', 'major', 'organization')
    search_fields = ('name', 'normalized_name')
    raw_id_fields = ('organization', 'created_by')
    readonly_fields = ('normalized_name', 'created_at', 'updated_at')
    list_select_related = ('organization',)

    @admin.display(description='دامنه', ordering='organization')
    def scope_label(self, obj: Subject) -> str:
        return str(obj.organization) if obj.organization_id else 'سراسری'

    def save_model(self, request, obj, form, change):
        if not change and obj.created_by_id is None:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(AdvisoryEngagement)
class AdvisoryEngagementAdmin(admin.ModelAdmin):
    list_display = ('advisor', 'student', 'mode', 'status', 'started_on', 'invited_at')
    list_filter = ('status', 'mode', 'organization')
    search_fields = ('advisor__username', 'student__username', 'invited_phone')
    raw_id_fields = ('advisor', 'student', 'organization')
    list_select_related = ('advisor', 'student', 'organization')
    date_hierarchy = 'invited_at'
    # invited_phone is the anchor of the accept-time re-verification (B6): editing
    # it here would let an operator redirect an invite at a different account.
    readonly_fields = ('invited_at', 'invited_phone', 'terms_accepted_at')

    def has_add_permission(self, request) -> bool:
        return False


@admin.register(StudentSubject)
class StudentSubjectAdmin(admin.ModelAdmin):
    """Read-mostly inspection surface for a student's subject selection.

    The write path is the advisor's picker, not this page — but a support operator
    debugging "my advisor's subjects vanished" needs to see the *deactivated* rows
    the set-replace leaves behind, which the API deliberately hides. ``is_active`` is
    editable here on purpose so an operator can hand-reactivate one; ``engagement`` and
    ``subject`` are ``raw_id_fields`` because both catalogs are far too large for a
    dropdown.
    """

    list_display = ('subject', 'engagement', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('subject__name', 'engagement__student__username')
    raw_id_fields = ('engagement', 'subject')
    readonly_fields = ('created_at', 'updated_at')
    list_select_related = ('subject', 'engagement', 'engagement__student')


class DailyLogItemInline(admin.TabularInline):
    """The day's minutes, inline under the day.

    Not registered as a page of its own: an item is meaningless without its log, and
    a standalone changelist of ``actual_minutes`` rows would be a support tool that
    invites reading many students' study habits side by side — exactly the aggregate
    view D1 keeps away from everyone but the student and their own advisor.
    """

    model = DailyLogItem
    extra = 0
    raw_id_fields = ('student_subject',)
    readonly_fields = ('created_at', 'updated_at')
    # Only reachable on the backend host, but an operator retyping a student's
    # reported minutes would silently corrupt the S8 commitment ratio and there is no
    # audit trail to notice it by. Inspection only.
    can_delete = False

    def has_add_permission(self, request, obj) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False


@admin.register(DailyLog)
class DailyLogAdmin(admin.ModelAdmin):
    """Read-only support view of a student's own report of a day.

    Deliberately not writable anywhere on this page. This is the *student's* account
    of their own day (D3), and the S8 metric divides by it: an operator "fixing" a
    number here would produce a commitment percentage that neither the student nor
    their advisor could account for. Support needs to *see* the day to answer «my
    yesterday vanished» — nothing more.

    Retention (D2) is 730 days and is documented, not automated: no sweeper exists
    yet, so this page is currently also the answer to "how far back does it go".
    """

    list_display = ('log_date', 'engagement', 'mood', 'total_minutes', 'updated_at')
    list_filter = ('mood',)
    search_fields = ('engagement__student__username', 'engagement__advisor__username')
    raw_id_fields = ('engagement',)
    date_hierarchy = 'log_date'
    list_select_related = ('engagement', 'engagement__student')
    inlines = [DailyLogItemInline]
    readonly_fields = ('engagement', 'log_date', 'mood', 'note', 'created_at', 'updated_at')

    def get_queryset(self, request):
        # The changelist renders ``total_minutes`` per row; without this the page is
        # one extra query per day shown.
        return super().get_queryset(request).prefetch_related('items')

    @admin.display(description='مجموع دقیقه‌ها')
    def total_minutes(self, obj: DailyLog) -> int:
        return sum(item.actual_minutes for item in obj.items.all())

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False


@admin.register(AdvisoryAccessLog)
class AdvisoryAccessLogAdmin(admin.ModelAdmin):
    """Read-only audit surface for D4 — who read which engagement's data, when.

    Fully read-only like ``DailyLogAdmin``, and for a starker reason: this is an
    audit trail. An operator editing or planting a row would corrupt the only
    answer the platform has to «who looked at this student», so nothing here can
    be added, changed or deleted. Rows are appended by
    ``services.study_plans.record_study_feed_view`` and by nothing else.
    """

    list_display = ('action', 'engagement', 'reader', 'accessed_at')
    search_fields = (
        'engagement__student__username',
        'engagement__advisor__username',
        'reader__username',
        'action',
    )
    raw_id_fields = ('engagement', 'reader')
    date_hierarchy = 'accessed_at'
    list_select_related = ('engagement', 'engagement__student', 'reader')
    readonly_fields = ('reader', 'engagement', 'action', 'accessed_at')

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
