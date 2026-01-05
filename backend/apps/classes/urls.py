from django.urls import path

from .views import (
    ClassPrerequisiteListView,
    ClassCreationSessionPublishView,
    ClassCreationSessionDetailView,
    ClassCreationSessionListView,
    ClassInvitationDetailView,
    ClassInvitationListCreateView,
    Step1TranscribeView,
    Step2StructureView,
    Step3PrerequisitesView,
    Step4PrerequisiteTeachingView,
    TeacherAnalyticsActivitiesView,
    TeacherAnalyticsChartView,
    TeacherAnalyticsDistributionView,
    TeacherAnalyticsStatsView,
)

urlpatterns = [
    path('creation-sessions/step-1/', Step1TranscribeView.as_view(), name='class_creation_step1'),
    path('creation-sessions/step-2/', Step2StructureView.as_view(), name='class_creation_step2'),
    path('creation-sessions/step-3/', Step3PrerequisitesView.as_view(), name='class_creation_step3'),
    path('creation-sessions/step-4/', Step4PrerequisiteTeachingView.as_view(), name='class_creation_step4'),

    path('creation-sessions/', ClassCreationSessionListView.as_view(), name='class_creation_session_list'),
    path('creation-sessions/<int:session_id>/', ClassCreationSessionDetailView.as_view(), name='class_creation_session_detail'),
    path('creation-sessions/<int:session_id>/publish/', ClassCreationSessionPublishView.as_view(), name='class_creation_session_publish'),
    path('creation-sessions/<int:session_id>/prerequisites/', ClassPrerequisiteListView.as_view(), name='class_creation_session_prerequisites'),
    path('creation-sessions/<int:session_id>/invites/', ClassInvitationListCreateView.as_view(), name='class_creation_session_invites'),
    path('creation-sessions/<int:session_id>/invites/<int:invite_id>/', ClassInvitationDetailView.as_view(), name='class_creation_session_invite_detail'),

    path('teacher/analytics/stats/', TeacherAnalyticsStatsView.as_view(), name='teacher_analytics_stats'),
    path('teacher/analytics/chart/', TeacherAnalyticsChartView.as_view(), name='teacher_analytics_chart'),
    path('teacher/analytics/distribution/', TeacherAnalyticsDistributionView.as_view(), name='teacher_analytics_distribution'),
    path('teacher/analytics/activities/', TeacherAnalyticsActivitiesView.as_view(), name='teacher_analytics_activities'),
]
