import os

from django.apps import AppConfig


class ClassesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.classes'

    def ready(self):
        # Source-aware V4 is the production path. OCR4 source-first geometry is
        # enabled unless the deployment explicitly opts out. This is set before
        # importing tasks_v4 so web/worker processes share the same default.
        # Emergency rollback: EXAM_PREP_V4_SOURCE_FIRST_ENABLED=0.
        os.environ.setdefault('EXAM_PREP_V4_SOURCE_FIRST_ENABLED', '1')

        from . import models_v4  # noqa: F401
        from . import models_v4_blocks  # noqa: F401
        from . import models_v4_records  # noqa: F401
        from . import models_v4_review  # noqa: F401
        from . import models_v4_projection  # noqa: F401
        from . import models_v4_bridge  # noqa: F401
        from . import signals  # noqa: F401
        from . import tasks_exam_prep  # noqa: F401
        from . import tasks_v4  # noqa: F401
        from . import tasks_v4_recovery  # noqa: F401

        # Deadline-focused release hardening: conservative OCR4 answer-label
        # evidence + teacher-curated semantic projection edits.  The installer
        # patches existing service seams after their modules are loaded.
        from .services.exam_prep_v4_deployment_hardening import install

        install()
