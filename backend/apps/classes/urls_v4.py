from django.urls import path

from apps.classes.views_v4 import (
    ExamPrepV4BatchUploadView,
    ExamPrepV4PageThumbnailView,
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
    path(
        (
            'projects/<int:project_id>/documents/<int:document_id>/'
            'pages/<int:page_number>/thumbnail/'
        ),
        ExamPrepV4PageThumbnailView.as_view(),
        name='project-page-thumbnail',
    ),
]
