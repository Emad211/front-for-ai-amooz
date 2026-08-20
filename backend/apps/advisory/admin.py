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
"""

from django.contrib import admin

from .models import AdvisoryEngagement, StudentSubject, Subject


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'grade', 'scope_label', 'is_active', 'created_at')
    list_filter = ('is_active', 'grade', 'organization')
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
