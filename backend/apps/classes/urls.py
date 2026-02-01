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
    Step5RecapView,
    TeacherAnalyticsActivitiesView,
    TeacherAnalyticsChartView,
    TeacherAnalyticsDistributionView,
    TeacherAnalyticsStatsView,
    TeacherStudentsListView,
    StudentCourseListView,
    StudentCourseContentView,
    StudentCoursePdfExportView,
    StudentCourseChatView,
    StudentCourseChatMediaView,
    StudentCourseChatHistoryView,
    StudentChapterQuizView,
    StudentFinalExamView,
    InviteCodeVerifyView,
    # Exam Prep Pipeline views
    ExamPrepStep1TranscribeView,
    ExamPrepStep2StructureView,
    ExamPrepSessionDetailView,
    ExamPrepSessionListView,
    ExamPrepSessionPublishView,
    ExamPrepInvitationListCreateView,
    ExamPrepInvitationDetailView,
    # Student Exam Prep views
    StudentExamPrepListView,
    StudentExamPrepDetailView,
    StudentExamPrepSubmitView,
)

urlpatterns = [
    # Class Pipeline (5 steps)
    path('creation-sessions/step-1/', Step1TranscribeView.as_view(), name='class_creation_step1'),
    path('creation-sessions/step-2/', Step2StructureView.as_view(), name='class_creation_step2'),
    path('creation-sessions/step-3/', Step3PrerequisitesView.as_view(), name='class_creation_step3'),
    path('creation-sessions/step-4/', Step4PrerequisiteTeachingView.as_view(), name='class_creation_step4'),
    path('creation-sessions/step-5/', Step5RecapView.as_view(), name='class_creation_step5'),

    path('creation-sessions/', ClassCreationSessionListView.as_view(), name='class_creation_session_list'),
    path('creation-sessions/<int:session_id>/', ClassCreationSessionDetailView.as_view(), name='class_creation_session_detail'),
    path('creation-sessions/<int:session_id>/publish/', ClassCreationSessionPublishView.as_view(), name='class_creation_session_publish'),
    path('creation-sessions/<int:session_id>/prerequisites/', ClassPrerequisiteListView.as_view(), name='class_creation_session_prerequisites'),
    path('creation-sessions/<int:session_id>/invites/', ClassInvitationListCreateView.as_view(), name='class_creation_session_invites'),
    path('creation-sessions/<int:session_id>/invites/<int:invite_id>/', ClassInvitationDetailView.as_view(), name='class_creation_session_invite_detail'),

    # Exam Prep Pipeline (2 steps)
    path('exam-prep-sessions/step-1/', ExamPrepStep1TranscribeView.as_view(), name='exam_prep_step1'),
    path('exam-prep-sessions/step-2/', ExamPrepStep2StructureView.as_view(), name='exam_prep_step2'),
    path('exam-prep-sessions/', ExamPrepSessionListView.as_view(), name='exam_prep_session_list'),
    path('exam-prep-sessions/<int:session_id>/', ExamPrepSessionDetailView.as_view(), name='exam_prep_session_detail'),
    path('exam-prep-sessions/<int:session_id>/publish/', ExamPrepSessionPublishView.as_view(), name='exam_prep_session_publish'),
    path('exam-prep-sessions/<int:session_id>/invites/', ExamPrepInvitationListCreateView.as_view(), name='exam_prep_session_invites'),
    path('exam-prep-sessions/<int:session_id>/invites/<int:invite_id>/', ExamPrepInvitationDetailView.as_view(), name='exam_prep_session_invite_detail'),

    # Student Exam Prep endpoints
    path('student/exam-preps/', StudentExamPrepListView.as_view(), name='student_exam_prep_list'),
    path('student/exam-preps/<int:session_id>/', StudentExamPrepDetailView.as_view(), name='student_exam_prep_detail'),
    path('student/exam-preps/<int:session_id>/submit/', StudentExamPrepSubmitView.as_view(), name='student_exam_prep_submit'),

    # Teacher Analytics
    path('teacher/analytics/stats/', TeacherAnalyticsStatsView.as_view(), name='teacher_analytics_stats'),
    path('teacher/analytics/chart/', TeacherAnalyticsChartView.as_view(), name='teacher_analytics_chart'),
    path('teacher/analytics/distribution/', TeacherAnalyticsDistributionView.as_view(), name='teacher_analytics_distribution'),
    path('teacher/analytics/activities/', TeacherAnalyticsActivitiesView.as_view(), name='teacher_analytics_activities'),

    # Teacher Students
    path('teacher/students/', TeacherStudentsListView.as_view(), name='teacher_students_list'),

    # Student endpoints
    path('student/courses/', StudentCourseListView.as_view(), name='student_courses_list'),
    path('student/courses/<int:session_id>/content/', StudentCourseContentView.as_view(), name='student_course_content'),
    path('student/courses/<int:session_id>/export-pdf/', StudentCoursePdfExportView.as_view(), name='student_course_export_pdf'),
    path('student/courses/<int:session_id>/chat/', StudentCourseChatView.as_view(), name='student_course_chat'),
    path('student/courses/<int:session_id>/chat-media/', StudentCourseChatMediaView.as_view(), name='student_course_chat_media'),
    path('student/courses/<int:session_id>/chat-history/', StudentCourseChatHistoryView.as_view(), name='student_course_chat_history'),
    path('student/courses/<int:session_id>/chapters/<str:chapter_id>/quiz/', StudentChapterQuizView.as_view(), name='student_chapter_quiz'),
    path('student/courses/<int:session_id>/final-exam/', StudentFinalExamView.as_view(), name='student_final_exam'),

    path('invites/verify/', InviteCodeVerifyView.as_view(), name='invite_code_verify'),
]
