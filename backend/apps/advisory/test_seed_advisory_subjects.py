"""Step 8 — the ``seed_advisory_subjects`` management command.

Zero-token, no-network. This command is the *only* writer of the national
(``organization = NULL``) ``Subject`` catalog, and the advisor picker derives a
student's candidate subjects from it (``services/scope.curriculum_subjects``).
So a silent half-seed, or a re-run that clobbers an admin's orthographic fix,
would stay invisible until an advisor noticed a missing subject. These tests pin
the three properties that keep it honest: validate-the-whole-file-first,
idempotent-by-identity (not by name), and no-clobber on re-run.
"""

from __future__ import annotations

import json
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.advisory.models import Subject
from apps.advisory.services.text import normalize_subject_name

pytestmark = pytest.mark.django_db


def _write(tmp_path: Path, subjects: list, *, name: str = 'curriculum.json') -> str:
    path = tmp_path / name
    path.write_text(json.dumps({'version': 1, 'subjects': subjects}), encoding='utf-8')
    return str(path)


def _seed(path: str, **kwargs) -> str:
    out = StringIO()
    call_command('seed_advisory_subjects', '--file', path, stdout=out, **kwargs)
    return out.getvalue()


# ── happy path ────────────────────────────────────────────────────────────────

def test_seeds_national_subjects(tmp_path):
    path = _write(tmp_path, [
        {'name': 'حسابان', 'grade': '11', 'major': 'math'},
        {'name': 'زیست‌شناسی', 'grade': '11', 'major': 'science'},
    ])
    _seed(path)

    assert Subject.objects.count() == 2
    s = Subject.objects.get(normalized_name=normalize_subject_name('حسابان'))
    assert s.grade == '11'
    assert s.major == 'math'
    assert s.organization_id is None       # national
    assert s.is_active is True


def test_general_subject_has_null_major(tmp_path):
    # major omitted / explicit null → a *general* subject shared across every major.
    path = _write(tmp_path, [
        {'name': 'دین و زندگی', 'grade': '12'},
        {'name': 'زبان انگلیسی', 'grade': '12', 'major': None},
    ])
    _seed(path)

    assert Subject.objects.filter(major__isnull=True).count() == 2


# ── idempotency & identity ──────────────────────────────────────────────────

def test_rerun_creates_nothing(tmp_path):
    path = _write(tmp_path, [{'name': 'فیزیک', 'grade': '10', 'major': 'science'}])
    _seed(path)
    _seed(path)      # second run against the same file
    assert Subject.objects.count() == 1


def test_same_name_different_grade_are_two_rows(tmp_path):
    # Identity is the (name, grade, major) tuple — the same subject name in two
    # grades is two distinct rows, not a collision.
    path = _write(tmp_path, [
        {'name': 'ریاضی', 'grade': '10', 'major': 'math'},
        {'name': 'ریاضی', 'grade': '11', 'major': 'math'},
    ])
    _seed(path)
    assert Subject.objects.count() == 2


def test_rerun_does_not_clobber_admin_edit(tmp_path):
    # The seed file carries a spacing variant; an admin later fixes the display
    # spelling. The fix is orthographic — normalized identity is unchanged — so the
    # re-seed matches the existing row and must leave the admin's display name alone.
    path = _write(tmp_path, [{'name': 'زیست شناسی', 'grade': '11', 'major': 'science'}])
    _seed(path)

    obj = Subject.objects.get(grade='11', major='science')
    obj.name = 'زیست‌شناسی'      # ZWNJ instead of a space → same normalized_name
    obj.save()
    assert obj.normalized_name == normalize_subject_name('زیست شناسی')  # identity held

    _seed(path)                  # re-seed with the original spacing
    obj.refresh_from_db()
    assert obj.name == 'زیست‌شناسی'    # admin's display edit survives
    assert Subject.objects.count() == 1


def test_normalization_dedupes_across_runs(tmp_path):
    # Arabic ي vs Persian ی fold to the same identity, so the second file is a no-op.
    _seed(_write(tmp_path, [{'name': 'عربي', 'grade': '10', 'major': 'humanities'}], name='a.json'))
    _seed(_write(tmp_path, [{'name': 'عربی', 'grade': '10', 'major': 'humanities'}], name='b.json'))
    assert Subject.objects.count() == 1


# ── validate-first: one bad row blocks the whole seed ───────────────────────

def test_invalid_grade_writes_nothing(tmp_path):
    path = _write(tmp_path, [
        {'name': 'خوب', 'grade': '10', 'major': 'math'},
        {'name': 'بد', 'grade': '99', 'major': 'math'},     # 99 ∉ SUBJECT_GRADE_CHOICES
    ])
    with pytest.raises(CommandError):
        _seed(path)
    assert Subject.objects.count() == 0      # the good row did NOT slip in

def test_missing_grade_rejected(tmp_path):
    # A gradeless subject derives for nobody, so it is rejected rather than stored.
    path = _write(tmp_path, [{'name': 'بی‌پایه', 'major': 'math'}])
    with pytest.raises(CommandError):
        _seed(path)
    assert Subject.objects.count() == 0


def test_invalid_major_rejected(tmp_path):
    path = _write(tmp_path, [{'name': 'درس', 'grade': '10', 'major': 'art'}])
    with pytest.raises(CommandError):
        _seed(path)
    assert Subject.objects.count() == 0


def test_missing_name_rejected(tmp_path):
    path = _write(tmp_path, [{'grade': '10', 'major': 'math'}])
    with pytest.raises(CommandError):
        _seed(path)
    assert Subject.objects.count() == 0


# ── dry-run & missing file ──────────────────────────────────────────────────

def test_dry_run_writes_nothing(tmp_path):
    path = _write(tmp_path, [{'name': 'آمار', 'grade': '11', 'major': 'math'}])
    out = _seed(path, dry_run=True)
    assert Subject.objects.count() == 0
    assert 'dry-run' in out


def test_missing_file_errors(tmp_path):
    with pytest.raises(CommandError):
        _seed(str(tmp_path / 'does-not-exist.json'))


# ── the shipped catalog (Step 9): the real file must seed clean & idempotent ──

def test_shipped_national_curriculum_seeds_fully_and_idempotently():
    """The version-controlled ``national_curriculum.json`` is the real national
    catalog (180 rows after the Step 9 conversion rules). It must validate whole,
    create exactly its row count on a fresh DB, and re-seed as a strict no-op —
    the same idempotency proof the deployment run makes by hand."""
    from apps.advisory.management.commands.seed_advisory_subjects import DEFAULT_DATA_FILE

    first = _seed(str(DEFAULT_DATA_FILE))
    assert Subject.objects.count() == 180
    assert '180 created, 0 already present (180 rows in file)' in first

    second = _seed(str(DEFAULT_DATA_FILE))
    assert Subject.objects.count() == 180
    assert '0 created, 180 already present (180 rows in file)' in second
