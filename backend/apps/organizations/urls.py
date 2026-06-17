"""URL patterns for the organizations app."""

from django.urls import path

from . import views

app_name = 'organizations'

urlpatterns = [
    # ── Platform admin: org CRUD ─────────────────────────────────
    path('', views.OrganizationListCreateView.as_view(), name='org-list-create'),
    path('<int:org_pk>/', views.OrganizationDetailView.as_view(), name='org-detail'),

    # ── Org admin: member management ─────────────────────────────
    path('<int:org_pk>/members/', views.OrgMemberListView.as_view(), name='org-member-list'),
    path(
        '<int:org_pk>/members/<int:membership_pk>/',
        views.OrgMemberDetailView.as_view(),
        name='org-member-detail',
    ),

    # ── Org admin: invitation codes ──────────────────────────────
    path(
        '<int:org_pk>/invitation-codes/',
        views.OrgInviteCodeListCreateView.as_view(),
        name='org-invite-list-create',
    ),
    path(
        '<int:org_pk>/invitation-codes/<int:code_pk>/',
        views.OrgInviteCodeDetailView.as_view(),
        name='org-invite-detail',
    ),

    # ── Org admin: dashboard stats ───────────────────────────────
    path('<int:org_pk>/dashboard/', views.OrgDashboardView.as_view(), name='org-dashboard'),

    # ── Study groups (گروه آموزشی) ───────────────────────────────
    path(
        '<int:org_pk>/study-groups/',
        views.StudyGroupListCreateView.as_view(),
        name='study-group-list-create',
    ),
    path(
        '<int:org_pk>/study-groups/<int:group_pk>/',
        views.StudyGroupDetailView.as_view(),
        name='study-group-detail',
    ),
    path(
        '<int:org_pk>/study-groups/<int:group_pk>/teachers/',
        views.StudyGroupTeacherView.as_view(),
        name='study-group-teacher-add',
    ),
    path(
        '<int:org_pk>/study-groups/<int:group_pk>/teachers/<int:user_id>/',
        views.StudyGroupTeacherView.as_view(),
        name='study-group-teacher-remove',
    ),
    path(
        '<int:org_pk>/study-groups/<int:group_pk>/students/',
        views.StudyGroupStudentView.as_view(),
        name='study-group-student-add',
    ),
    path(
        '<int:org_pk>/study-groups/<int:group_pk>/students/<int:user_id>/',
        views.StudyGroupStudentView.as_view(),
        name='study-group-student-remove',
    ),
    path(
        '<int:org_pk>/my-study-groups/',
        views.MyStudyGroupsView.as_view(),
        name='my-study-groups',
    ),

    # ── Manager oversight: all org classes + AI cost breakdown ───
    path('<int:org_pk>/classes/', views.OrgClassesView.as_view(), name='org-classes'),
    path('<int:org_pk>/costs/', views.OrgCostsView.as_view(), name='org-costs'),

    # ── Invitation code validation & redemption ──────────────────
    path('validate-code/', views.ValidateInvitationView.as_view(), name='validate-code'),
    path('redeem-code/', views.RedeemInvitationView.as_view(), name='redeem-code'),

    # ── Workspace switcher ───────────────────────────────────────
    path('my-workspaces/', views.MyWorkspacesView.as_view(), name='my-workspaces'),
]
