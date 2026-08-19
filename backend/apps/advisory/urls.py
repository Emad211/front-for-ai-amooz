from django.urls import path

from .views import SubjectListView

urlpatterns = [
    path('subjects/', SubjectListView.as_view(), name='advisory_subject_list'),
]
