"""Seed the national-curriculum ``Subject`` catalog from a version-controlled file.

The advisor picker no longer offers a flat catalog: a student's candidate subjects
are *derived* from their own ``(grade, major)`` (see ``services/scope.curriculum_subjects``).
That derivation only returns something if the national curriculum has actually been
seeded — which is what this command does, from ``apps/advisory/data/national_curriculum.json``.

Idempotent by identity, not by name. A ``Subject``'s identity is the four-tuple
``(normalized_name, grade, major, organization)``; every row seeded here is national
(``organization = NULL``). So a re-run creates nothing new — it ``get_or_create``s on
that exact key. An existing row is left untouched, display name included: if a platform
admin renamed a subject in Django admin, re-seeding must not clobber their edit.

Dev note: ``seed_dev`` gives the demo student ``grade='12'/major='math'`` but seeds no
``Subject`` (seed_dev.py:151), so the advisor picker for that student is **empty** until
this command has run against a *filled* curriculum file. The shipped file is empty on
purpose (Step 9 of docs/features/advisor-mvp.md fills it), so a fresh checkout seeds
nothing and says so rather than failing.
"""

from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.advisory.models import Subject
from apps.advisory.services.text import normalize_subject_name

# apps/advisory/management/commands/<this> → parents[2] is the advisory app root.
DEFAULT_DATA_FILE = Path(__file__).resolve().parents[2] / 'data' / 'national_curriculum.json'


def _valid_codes(field_name: str) -> set[str]:
    """Accepted codes for a ``Subject`` choice field, read straight off the model.

    The import-boundary guard (test_import_boundaries.py) lets this file import
    only ``Subject`` from advisory.models — not the ``SUBJECT_*_CHOICES`` tuples.
    That is no loss: a field's ``choices`` *are* those tuples, so the field is the
    single source of truth for its codes and can't drift from what the DB accepts.
    """
    return {code for code, _label in Subject._meta.get_field(field_name).choices}


class Command(BaseCommand):
    help = (
        'Seed the national-curriculum Subject catalog (organization=NULL) from '
        'apps/advisory/data/national_curriculum.json. Idempotent; safe to re-run.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            default=str(DEFAULT_DATA_FILE),
            help='Path to the curriculum JSON (defaults to the version-controlled file).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Validate and report what would change, without writing anything.',
        )

    def handle(self, *args, **options):
        path = Path(options['file'])
        dry_run = options['dry_run']

        rows = self._load(path)
        if not rows:
            self.stdout.write(self.style.NOTICE(
                f'No subjects in {path} — nothing to seed. '
                f'Fill it in (advisor-mvp Step 9), then re-run.'
            ))
            return

        # Validate the WHOLE file before touching the database: a typo'd grade code
        # in one row must block the seed, not silently drop that one subject and
        # leave a hole nobody notices. Failing here beats a half-seeded catalog.
        cleaned, errors = self._validate(rows)
        if errors:
            raise CommandError(
                'Curriculum file has invalid rows; nothing was written:\n  - '
                + '\n  - '.join(errors)
            )

        self._warn_in_file_duplicates(cleaned)

        if dry_run:
            self._report_dry_run(cleaned)
            return

        created, existing = self._apply(cleaned)
        self.stdout.write(self.style.SUCCESS(
            f'Done. {created} created, {existing} already present '
            f'({len(cleaned)} rows in file).'
        ))

    # ── load ────────────────────────────────────────────────────────────────
    def _load(self, path: Path) -> list:
        try:
            raw = path.read_text(encoding='utf-8')
        except FileNotFoundError:
            raise CommandError(f'Curriculum file not found: {path}')
        except OSError as exc:
            raise CommandError(f'Could not read {path}: {exc}')

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CommandError(f'{path} is not valid JSON: {exc}')

        subjects = data.get('subjects') if isinstance(data, dict) else None
        if subjects is None:
            raise CommandError(f'{path} must be an object with a "subjects" array.')
        if not isinstance(subjects, list):
            raise CommandError(f'"subjects" in {path} must be an array.')
        return subjects

    # ── validate ──────────────────────────────────────────────────────────────
    def _validate(self, rows: list) -> tuple[list[dict], list[str]]:
        """Return (cleaned rows, error messages). Cleaned rows carry a precomputed
        ``key`` = (normalized_name, grade, major) for dedup/reporting."""
        cleaned: list[dict] = []
        errors: list[str] = []
        valid_grades = _valid_codes('grade')
        valid_majors = _valid_codes('major')

        for i, row in enumerate(rows):
            where = f'row {i}'
            if not isinstance(row, dict):
                errors.append(f'{where}: expected an object, got {type(row).__name__}.')
                continue

            name = str(row.get('name', '')).strip()
            if not name:
                errors.append(f'{where}: missing "name".')
                continue
            normalized = normalize_subject_name(name)
            if not normalized:
                errors.append(f'{where} ("{name}"): name normalizes to empty.')
                continue

            grade = row.get('grade')
            grade = str(grade).strip() if grade is not None else None
            if grade not in valid_grades:
                errors.append(
                    f'{where} ("{name}"): grade {grade!r} is not one of '
                    f'{sorted(valid_grades)} (grade is required — a gradeless '
                    f'subject derives for nobody).'
                )
                continue

            major = row.get('major')
            if isinstance(major, str):
                major = major.strip() or None
            if major is not None and major not in valid_majors:
                errors.append(
                    f'{where} ("{name}"): major {major!r} is not one of '
                    f'{sorted(valid_majors)} (use null / omit for a general subject).'
                )
                continue

            cleaned.append({
                'name': name,
                'grade': grade,
                'major': major,
                'normalized': normalized,
                'key': (normalized, grade, major),
            })

        return cleaned, errors

    def _warn_in_file_duplicates(self, cleaned: list[dict]) -> None:
        seen: set = set()
        dupes: set = set()
        for row in cleaned:
            if row['key'] in seen:
                dupes.add(row['key'])
            seen.add(row['key'])
        for normalized, grade, major in sorted(dupes):
            self.stdout.write(self.style.WARNING(
                f'Duplicate in file: normalized={normalized!r} grade={grade} '
                f'major={major} appears more than once (extras are no-ops).'
            ))

    # ── apply ───────────────────────────────────────────────────────────────
    @transaction.atomic
    def _apply(self, cleaned: list[dict]) -> tuple[int, int]:
        created_count = 0
        existing_count = 0
        for row in cleaned:
            # Lookup on the full national identity; organization is always NULL here.
            # save() recomputes normalized_name from name, so the value we pass and
            # the value stored agree — no drift even though it is in the lookup.
            _obj, created = Subject.objects.get_or_create(
                normalized_name=row['normalized'],
                grade=row['grade'],
                major=row['major'],
                organization=None,
                defaults={'name': row['name'], 'is_active': True},
            )
            if created:
                created_count += 1
            else:
                existing_count += 1
        return created_count, existing_count

    def _report_dry_run(self, cleaned: list[dict]) -> None:
        would_create = 0
        would_exist = 0
        for row in cleaned:
            exists = Subject.objects.filter(
                normalized_name=row['normalized'],
                grade=row['grade'],
                major=row['major'],
                organization__isnull=True,
            ).exists()
            if exists:
                would_exist += 1
            else:
                would_create += 1
        self.stdout.write(self.style.NOTICE(
            f'[dry-run] {would_create} would be created, {would_exist} already '
            f'present ({len(cleaned)} rows in file). Nothing written.'
        ))
