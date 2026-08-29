"""Advisory URL map.

The ``me/`` prefix marks the student's side of the feature. Everything without it
is the advisor's. That split is not cosmetic: it is how a reviewer sees at a glance
that ``IsStudentRole`` belongs on one group and ``IsAdvisorUser`` on the other,
without opening views.py.
"""

from django.urls import path, register_converter
from django.utils.dateparse import parse_date

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
from .views_exams import (
    AdvisorExamAnalysesView,
    AdvisorExamAnalysisDetailView,
    AdvisorExamScoreDetailView,
    AdvisorExamScoresView,
    StudentExamAnalysesView,
    StudentExamScoresView,
)
from .views_intake import AdvisorIntakeView, StudentIntakeView
from .views_monthly import (
    AdvisorCallLogsView,
    AdvisorChallengeDaysView,
    AdvisorChallengeDetailView,
    AdvisorChallengesView,
    AdvisorMonthlyOutlookView,
    AdvisorWeeklyAssessmentsView,
    StudentChallengeDaysView,
    StudentChallengesView,
    StudentMonthlyOutlookView,
)
from .views_overview import AdvisorOverviewView
from .views_org import (
    OrgAdvisoryOverviewView,
    OrgAdvisoryReportView,
    OrgReassignEngagementView,
)
from .views_folders import (
    AdvisorFolderDetailView,
    AdvisorFolderListView,
    AssignEngagementFolderView,
)


class ISODateConverter:
    """``<date:…>`` path segment: strict ``YYYY-MM-DD``, parsed once at routing.

    The restart plan's route table names a ``<date:month_start>`` converter
    that Django does not ship, so it is defined here next to the only routes
    that use it. An invalid calendar date (e.g. ``2026-02-30``) fails
    ``to_python`` and therefore 404s at routing time — the view never sees a
    non-date under a date-typed name.
    """

    regex = r'\d{4}-\d{2}-\d{2}'

    def to_python(self, value):
        return parse_date(value)

    def to_url(self, value):
        return value.isoformat() if hasattr(value, 'isoformat') else str(value)


register_converter(ISODateConverter, 'date')

urlpatterns = [
    path('subjects/', SubjectListView.as_view(), name='advisory_subject_list'),

    # advisor side
    path('overview/', AdvisorOverviewView.as_view(), name='advisory_overview'),
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
    # Restart wave 4, step 5: exam scores (list/create + detail + mirror).
    path(
        'students/<int:pk>/exam-scores/',
        AdvisorExamScoresView.as_view(),
        name='advisory_student_exam_scores',
    ),
    path(
        'students/<int:pk>/exam-scores/<int:score_id>/',
        AdvisorExamScoreDetailView.as_view(),
        name='advisory_student_exam_score_detail',
    ),
    # Restart wave 4, step 6: exam analyses (list/create + detail + mirror).
    path(
        'students/<int:pk>/exam-analyses/',
        AdvisorExamAnalysesView.as_view(),
        name='advisory_student_exam_analyses',
    ),
    path(
        'students/<int:pk>/exam-analyses/<int:analysis_id>/',
        AdvisorExamAnalysisDetailView.as_view(),
        name='advisory_student_exam_analysis_detail',
    ),
    # Restart wave 5, step 8: the monthly outlook (advisor read/write + mirror).
    path(
        'students/<int:pk>/monthly-outlooks/<date:month_start>/',
        AdvisorMonthlyOutlookView.as_view(),
        name='advisory_student_monthly_outlook',
    ),
    # Restart wave 5, step 9: challenges (advisor CRUD + days, student mirror).
    path(
        'students/<int:pk>/challenges/',
        AdvisorChallengesView.as_view(),
        name='advisory_student_challenges',
    ),
    path(
        'students/<int:pk>/challenges/<int:challenge_id>/',
        AdvisorChallengeDetailView.as_view(),
        name='advisory_student_challenge_detail',
    ),
    path(
        'students/<int:pk>/challenges/<int:challenge_id>/days/',
        AdvisorChallengeDaysView.as_view(),
        name='advisory_student_challenge_days',
    ),
    path('invites/', AdvisoryInviteCreateView.as_view(), name='advisory_invite_create'),

    # Risman step 1: advisor-owned student folders + the per-student move door.
    path('folders/', AdvisorFolderListView.as_view(), name='advisory_folder_list'),
    path(
        'folders/<int:folder_id>/',
        AdvisorFolderDetailView.as_view(),
        name='advisory_folder_detail',
    ),
    path(
        'students/<int:pk>/folder/',
        AssignEngagementFolderView.as_view(),
        name='advisory_student_folder_assign',
    ),

    # Risman step 3: the thin org-manager panel (org-scoped, manager-only).
    # Gated by IsOrgManager; tenancy resolves from the manager's own membership,
    # so everything below MUST answer a stranger's manager with 404-not-403.
    path('org/overview/', OrgAdvisoryOverviewView.as_view(), name='advisory_org_overview'),
    path(
        'org/advisors/',
        OrgAdvisoryReportView.as_view(),
        name='advisory_org_advisor_report',
    ),
    path(
        'org/engagements/<int:pk>/reassign/',
        OrgReassignEngagementView.as_view(),
        name='advisory_org_reassign',
    ),

    # student side
    path('me/engagement/', StudentEngagementView.as_view(), name='advisory_my_engagement'),
    path('me/subjects/', StudentSubjectsView.as_view(), name='advisory_my_subjects'),
    path('me/plans/', StudentPlansView.as_view(), name='advisory_my_plans'),
    # Restart wave 3, step 2: the student's own intake form.
    path('me/intake/', StudentIntakeView.as_view(), name='advisory_my_intake'),
    # Restart wave 4, step 5: the student's read-only exam-score mirror.
    path('me/exam-scores/', StudentExamScoresView.as_view(), name='advisory_my_exam_scores'),
    # Restart wave 4, step 6: the student's read-only analysis mirror.
    path(
        'me/exam-analyses/',
        StudentExamAnalysesView.as_view(),
        name='advisory_my_exam_analyses',
    ),
    # Restart wave 5, step 8: the student's read-only month-plan mirror.
    path(
        'me/monthly-outlooks/<date:month_start>/',
        StudentMonthlyOutlookView.as_view(),
        name='advisory_my_monthly_outlook',
    ),
    # Restart wave 5, step 9: the student's challenge mirror + daily fill-in.
    path('me/challenges/', StudentChallengesView.as_view(), name='advisory_my_challenges'),
    path(
        'me/challenges/<int:challenge_id>/days/',
        StudentChallengeDaysView.as_view(),
        name='advisory_my_challenge_days',
    ),
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

# Risman step 2 (reports): the module owns its urlpatterns (built self-contained
# for parallel delivery); wired here with a late import on purpose.
from .views_reports import urlpatterns as reports_urlpatterns  # noqa: E402

urlpatterns += reports_urlpatterns

# Risman step 3 (org panel): same late-import wiring as the reports module.
from .views_org import urlpatterns as org_urlpatterns  # noqa: E402

urlpatterns += org_urlpatterns

# Risman steps 5+6 (AI planner): same late-import wiring; the module owns its
# single ai-draft route (multipart-capable, so it sits in its own module).
from .views_ai_planner import urlpatterns as ai_planner_urlpatterns  # noqa: E402

urlpatterns += ai_planner_urlpatterns
