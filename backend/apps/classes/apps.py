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
        from .services import exam_prep_mistral_document_pipeline as mistral_engine

        original_question_record = mistral_engine._question_record

        def source_aware_question_record(region):
            record = original_question_record(region)
            if record is not None and mistral_engine._question_visual_required(region):
                issues = list(record.get('issues') or [])
                # The engine immediately satisfies this with the authoritative
                # PDF source crop and removes the temporary blocker afterward.
                if 'visual_evidence_required' not in issues:
                    issues.append('visual_evidence_required')
                record['issues'] = issues
            return record

        mistral_engine._question_record = source_aware_question_record
        tasks_exam_prep.run_exam_prep_pdf_pipeline = (
            mistral_engine.run_exam_prep_mistral_document_pipeline
        )
