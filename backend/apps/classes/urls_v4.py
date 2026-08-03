from django.urls import path

from apps.classes.views_v4 import (
    ExamPrepV4BatchUploadView,
    ExamPrepV4ProjectDetailView,
)


app_name = 'exam_prep_v4'

urlpatterns = [
    path(
        'projects/',
        ExamPrepV4BatchUploadView.as_view(),
        name='project-list-create',
    ),
    path(
        'projects/<int:project_id>/',
        ExamPrepV4ProjectDetailView.as_view(),
        name='project-source-map-detail',
    ),
]
