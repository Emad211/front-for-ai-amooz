"""Compatibility link between the existing teacher create flow and the source-aware engine."""
from django.db import models


class ExamV4SessionBridge(models.Model):
    project = models.OneToOneField(
        'classes.ExamProject',
        on_delete=models.CASCADE,
        related_name='create_flow_bridge',
    )
    session = models.OneToOneField(
        'classes.ClassCreationSession',
        on_delete=models.CASCADE,
        related_name='source_aware_exam_bridge',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'classes'
