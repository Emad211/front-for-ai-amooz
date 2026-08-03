from django.urls import path

from apps.classes.views_v4 import (
    ExamPrepV4BatchUploadView,
    ExamPrepV4PageThumbnailView,
    ExamPrepV4ProjectDetailView,
)
from apps.classes.views_v4_blocks import ExamPrepV4BlockListView
from apps.classes.views_v4_source_map import (
    ExamPrepV4SourceMapConfirmationView,
    ExamPrepV4SourceMapMutationView,
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
            'source-map/'
        ),
        ExamPrepV4SourceMapMutationView.as_view(),
        name='project-source-map-mutation',
    ),
    path(
        (
            'projects/<int:project_id>/documents/<int:document_id>/'
            'source-map/confirm/'
        ),
        ExamPrepV4SourceMapConfirmationView.as_view(),
        name='project-source-map-confirmation',
    ),
    path(
        (
            'projects/<int:project_id>/documents/<int:document_id>/'
            'blocks/'
        ),
        ExamPrepV4BlockListView.as_view(),
        name='project-source-block-list',
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
