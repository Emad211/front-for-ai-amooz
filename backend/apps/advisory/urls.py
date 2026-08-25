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
    AdvisorStudyFeedView,
    AdvisorStudyPlanDraftView,
    AdvisorStudyPlanPublishView,
    AdvisorStudyPlanUnpublishView,
    AdvisorStudyPlansView,
    AdvisoryInviteCreateView,
    StudentEngagementView,
    StudentInviteAcceptView,
    StudentInviteRejectView,
    StudentPlansView,
    StudentStudyLogView,
    StudentSubjectsView,
    SubjectListView,
)
from .views_intake import AdvisorIntakeView, StudentIntakeView
from .views_monthly import AdvisorCallLogsView, AdvisorWeeklyAssessmentsView

urlpatterns = [
    path('subjects/', SubjectListView.as_view(), name='advisory_subject_list'),

    # advisor side
    path('students/', AdvisorStudentListView.as_view(), name='advisory_student_list'),
    path(
        'students/<int:pk>/subjects/',
        AdvisorEngagementSubjectsView.as_view(),
        name='advisory_student_subjects',
    ),
    path(
        'students/<int:pk>/study-feed/',
        AdvisorStudyFeedView.as_view(),
        name='advisory_student_study_feed',
    ),
    path(
        'students/<int:pk>/study-plan/draft/',
        AdvisorStudyPlanDraftView.as_view(),
        name='advisory_student_plan_draft',
    ),
    path(
        'students/<int:pk>/study-plan/draft/publish/',
        AdvisorStudyPlanPublishView.as_view(),
        name='advisory_student_plan_publish',
    ),
    path(
        'students/<int:pk>/study-plan/<int:plan_id>/unpublish/',
        AdvisorStudyPlanUnpublishView.as_view(),
        name='advisory_student_plan_unpublish',
    ),
    path(
        'students/<int:pk>/study-plans/',
        AdvisorStudyPlansView.as_view(),
        name='advisory_student_plans',
    ),
    # Restart wave 3 (steps 2, 7, 10): intake, weekly assessments, call logs.
    path(
        'students/<int:pk>/intake/',
        AdvisorIntakeView.as_view(),
        name='advisory_student_intake',
    ),
    path(
        'students/<int:pk>/weekly-assessments/',
        AdvisorWeeklyAssessmentsView.as_view(),
        name='advisory_student_weekly_assessments',
    ),
    path(
        'students/<int:pk>/call-logs/',
        AdvisorCallLogsView.as_view(),
        name='advisory_student_call_logs',
    ),
    path('invites/', AdvisoryInviteCreateView.as_view(), name='advisory_invite_create'),

    # student side
    path('me/engagement/', StudentEngagementView.as_view(), name='advisory_my_engagement'),
    path('me/subjects/', StudentSubjectsView.as_view(), name='advisory_my_subjects'),
    path('me/plans/', StudentPlansView.as_view(), name='advisory_my_plans'),
    # Restart wave 3, step 2: the student's own intake form.
    path('me/intake/', StudentIntakeView.as_view(), name='advisory_my_intake'),
    # One route, no ``<date>`` segment: the day is a query parameter because the
    # resource is "my log" and the date selects a slice of it. A path segment would
    # read like an addressable row and invite the sibling URL that does not exist —
    # someone else's day.
    path('me/study-log/', StudentStudyLogView.as_view(), name='advisory_my_study_log'),
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
