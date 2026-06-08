"""Django admin registration for the organizations app."""

from django.contrib import admin

from .models import (
    InvitationCode,
    Organization,
    OrganizationMembership,
    StudyGroup,
    StudyGroupMembership,
    StudyGroupTeacher,
)


class OrganizationMembershipInline(admin.TabularInline):
    model = OrganizationMembership
    extra = 0
    raw_id_fields = ('user',)
    readonly_fields = ('joined_at',)


class InvitationCodeInline(admin.TabularInline):
    model = InvitationCode
    extra = 0
    raw_id_fields = ('created_by',)
    readonly_fields = ('code', 'use_count', 'created_at')


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'subscription_status', 'student_capacity', 'current_student_count', 'created_at')
    list_filter = ('subscription_status',)
    search_fields = ('name', 'slug')
    raw_id_fields = ('owner',)
    inlines = [OrganizationMembershipInline, InvitationCodeInline]


@admin.register(OrganizationMembership)
class OrganizationMembershipAdmin(admin.ModelAdmin):
    list_display = ('user', 'organization', 'org_role', 'status', 'joined_at')
    list_filter = ('org_role', 'status')
    search_fields = ('user__username', 'user__email', 'internal_id')
    raw_id_fields = ('user', 'organization')


@admin.register(InvitationCode)
class InvitationCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'organization', 'target_role', 'is_active', 'use_count', 'max_uses', 'expires_at')
    list_filter = ('target_role', 'is_active')
    search_fields = ('code', 'label')
    raw_id_fields = ('organization', 'created_by')
    readonly_fields = ('code', 'use_count')


class StudyGroupTeacherInline(admin.TabularInline):
    model = StudyGroupTeacher
    extra = 0
    raw_id_fields = ('teacher', 'assigned_by')
    readonly_fields = ('assigned_at',)


class StudyGroupMembershipInline(admin.TabularInline):
    model = StudyGroupMembership
    extra = 0
    raw_id_fields = ('student', 'added_by')
    readonly_fields = ('joined_at',)


@admin.register(StudyGroup)
class StudyGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'organization', 'grade_label', 'subject', 'status', 'created_at')
    list_filter = ('status', 'organization')
    search_fields = ('name', 'subject', 'grade_label')
    raw_id_fields = ('organization', 'created_by')
    inlines = [StudyGroupTeacherInline, StudyGroupMembershipInline]
