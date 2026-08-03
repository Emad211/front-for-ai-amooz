from django.apps import AppConfig


class ClassesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.classes'

    def ready(self):
        # V4 is additive and isolated while the legacy classes model module
        # remains stable. Importing here registers the V4 models under the
        # existing ``classes`` app before checks, migrations, and requests run.
        from . import models_v4  # noqa: F401
        from . import models_v4_blocks  # noqa: F401
        from . import models_v4_records  # noqa: F401
        from . import models_v4_review  # noqa: F401
        from . import models_v4_projection  # noqa: F401
        from . import signals  # noqa: F401
        from . import tasks_v4  # noqa: F401
