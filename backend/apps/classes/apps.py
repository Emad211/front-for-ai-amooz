from django.apps import AppConfig


class ClassesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.classes'

    def ready(self):
        # Keep V4 model/task registration for already-created legacy V4 data,
        # but it is not the new Exam Prep intake or production engine.
        from . import models_v4  # noqa: F401
        from . import models_v4_blocks  # noqa: F401
        from . import models_v4_records  # noqa: F401
        from . import models_v4_review  # noqa: F401
        from . import models_v4_projection  # noqa: F401
        from . import models_v4_bridge  # noqa: F401
        from . import signals  # noqa: F401
        from . import tasks_exam_prep
        from . import tasks_v4  # noqa: F401
        from . import tasks_v4_recovery  # noqa: F401

        # New Exam Prep creation stays on the simple ClassCreationSession task,
        # but its extraction engine is the researched full-document Mistral
        # OCR4 pipeline (not V4 source-map/page-confirmation).
        from .services.exam_prep_mistral_document_pipeline import (
            run_exam_prep_mistral_document_pipeline,
        )

        tasks_exam_prep.run_exam_prep_pdf_pipeline = (
            run_exam_prep_mistral_document_pipeline
        )
