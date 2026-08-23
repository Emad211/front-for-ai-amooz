from django.apps import AppConfig
from django.core.management import call_command
from django.db.models.signals import post_migrate


class AdvisoryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.advisory'
    verbose_name = 'مشاوره و برنامه‌ریزی'

    def ready(self) -> None:
        # Auto-seed the national-curriculum Subject catalog after every
        # `migrate` that touches this app. Production's Docker entrypoint runs
        # `migrate` on every boot, so this is the hook that guarantees the
        # catalog exists without a manual `seed_advisory_subjects` step — its
        # absence left the live deployment with an empty Subject table, which
        # made every derived (grade, major) curriculum come back empty for both
        # the advisor picker and the student.
        post_migrate.connect(self._seed_subject_catalog, sender=self)

    @staticmethod
    def _seed_subject_catalog(**kwargs) -> None:
        # Idempotent by design: the command get_or_create's on the identity
        # four-tuple (normalized_name, grade, major, organization), so a re-run
        # on every deploy writes nothing new. The shipped JSON file is validated
        # wholesale by the command (and by test_seed_advisory_subjects), so a
        # failure here is a real data bug and is allowed to surface loudly
        # instead of silently leaving the catalog empty again.
        call_command('seed_advisory_subjects', verbosity=0)
