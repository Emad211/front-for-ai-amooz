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

    # ── Invitation code validation & redemption ──────────────────
    path('validate-code/', views.ValidateInvitationView.as_view(), name='validate-code'),
    path('redeem-code/', views.RedeemInvitationView.as_view(), name='redeem-code'),

    # ── Workspace switcher ───────────────────────────────────────
    path('my-workspaces/', views.MyWorkspacesView.as_view(), name='my-workspaces'),
]
