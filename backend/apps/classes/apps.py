from django.apps import AppConfig


class ClassesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.classes'

    def ready(self):
        # Source-aware exam preparation remains registered only for existing
        # drafts during the staged cleanup. New intake uses tasks_exam_prep.
        from . import models_v4  # noqa: F401
        from . import models_v4_blocks  # noqa: F401
        from . import models_v4_records  # noqa: F401
        from . import models_v4_review  # noqa: F401
        from . import models_v4_projection  # noqa: F401
        from . import models_v4_bridge  # noqa: F401
        from . import signals  # noqa: F401
        from . import tasks_exam_prep  # noqa: F401
