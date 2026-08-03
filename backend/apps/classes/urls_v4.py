from django.urls import path

from apps.classes.views_v4 import ExamPrepV4BatchUploadView


app_name = 'exam_prep_v4'

urlpatterns = [
    path(
        'projects/',
        ExamPrepV4BatchUploadView.as_view(),
        name='project-batch-upload',
    ),
]
