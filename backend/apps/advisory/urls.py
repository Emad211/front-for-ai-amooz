"""Advisory URL map.

The ``me/`` prefix marks the student's side of the feature. Everything without it
is the advisor's. That split is not cosmetic: it is how a reviewer sees at a glance
that ``IsStudentRole`` belongs on one group and ``IsAdvisorUser`` on the other,
without opening views.py.
"""

from django.urls import path

from .views import (
    AdvisorEngagementSubjectsView,
    AdvisorStudentListView,
    AdvisoryInviteCreateView,
    StudentEngagementView,
    StudentInviteAcceptView,
    StudentInviteRejectView,
    StudentSubjectsView,
    SubjectListView,
)

urlpatterns = [
    path('subjects/', SubjectListView.as_view(), name='advisory_subject_list'),

    # advisor side
    path('students/', AdvisorStudentListView.as_view(), name='advisory_student_list'),
    path(
        'students/<int:pk>/subjects/',
        AdvisorEngagementSubjectsView.as_view(),
        name='advisory_student_subjects',
    ),
    path('invites/', AdvisoryInviteCreateView.as_view(), name='advisory_invite_create'),

    # student side
    path('me/engagement/', StudentEngagementView.as_view(), name='advisory_my_engagement'),
    path('me/subjects/', StudentSubjectsView.as_view(), name='advisory_my_subjects'),
    path(
        'me/invites/<int:pk>/accept/',
        StudentInviteAcceptView.as_view(),
        name='advisory_invite_accept',
    ),
    path(
        'me/invites/<int:pk>/reject/',
        StudentInviteRejectView.as_view(),
        name='advisory_invite_reject',
    ),
]
