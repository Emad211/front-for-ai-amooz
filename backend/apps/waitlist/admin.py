from django.contrib import admin

from .models import AccessRequest


@admin.register(AccessRequest)
class AccessRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'kind', 'display_name', 'phone', 'status', 'created_at')
    list_filter = ('kind', 'status', 'created_at')
    search_fields = ('full_name', 'org_name', 'phone', 'email')
    readonly_fields = ('created_at', 'updated_at', 'registration_token', 'token_consumed_at')
    date_hierarchy = 'created_at'

    @admin.display(description='نام')
    def display_name(self, obj: AccessRequest) -> str:
        return obj.org_name or obj.full_name
