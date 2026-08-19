"""Django admin for the advisory app.

The ``Subject`` catalog has no write API in the MVP on purpose: it is curated
slowly by a platform admin, not authored by advisors. Django admin *is* the
write surface, which means it is reachable only on the backend host — the
frontend rewrite does not proxy ``/admin/`` (see E3 in the spec).
"""

from django.contrib import admin

from .models import Subject


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'scope_label', 'is_active', 'created_at')
    list_filter = ('is_active', 'organization')
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
