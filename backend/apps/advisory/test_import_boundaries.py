"""S2 — two architectural boundaries, enforced by reading the AST (zero tokens).

Both are the kind of rule that a reviewer forgets and a linter does not know:

1. **``classes`` must never import ``advisory``.** advisory is the leaf; the
   dependency is one-way. If it ever reverses, the two largest subsystems in the
   repo become mutually dependent and neither can be changed alone.
2. **Only ``scope.py`` (plus admin/migrations/tests) may import a
   tenancy-bearing advisory model.** ``organizations`` shows what the other
   approach costs: one hand-rolled gate call repeated at ~19 sites, where a
   single forgotten call is a cross-tenant leak. Views ask ``scope.py`` for an
   already-scoped queryset instead.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

APPS_DIR = Path(__file__).resolve().parent.parent
ADVISORY_DIR = APPS_DIR / 'advisory'
CLASSES_DIR = APPS_DIR / 'classes'

# Models with no tenancy of their own. ``Subject`` is a shared catalog: it is not
# owned by a student, so listing it needs no engagement join and importing it
# directly leaks nothing. Every model added from step 3 on carries tenancy and
# must therefore stay out of this set.
_UNSCOPED = {'Subject'}

# scope.py is the door itself; admin and migrations are Django-owned surfaces that
# must import models by definition; tests exist to poke at models directly.
#
# The three write doors are added on purpose, and each *writes* tenancy rather than
# reading across it, so there is no queryset for scope.py to hand it:
#   • invites.py — creates the engagement row and runs the accept/reject state
#     machine under ``select_for_update``.
#   • student_subjects.py (S4) — the set-replace for a student's subject selection;
#     it mutates ``StudentSubject`` (get_or_create + is_active toggle) after the
#     view has already resolved ownership through scope.advisor_engagement.
#   • daily_logs.py (S5) — the set-replace for one day of a student's log; it
#     upserts ``DailyLog``/``DailyLogItem`` after the view has resolved the
#     engagement through scope.student_active_engagement, and re-checks D3 (only
#     the student themself may write) against that engagement.
#   • study_plans.py (S7, §14) — the draft upsert / publish / unpublish state
#     machine for ``StudyPlan``/``StudyPlanItem`` plus the append-only
#     ``AdvisoryAccessLog`` write; it mutates after the view has resolved the
#     engagement through scope.advisor_engagement.
#   • intake.py (restart step 2) — the set-replace for the intake form; it
#     rebuilds ``AdvisoryIntakeProfile``/``AdvisoryIntakeClass`` after the view
#     has resolved ownership through scope.advisor_engagement or
#     scope.student_active_engagement.
#   • assessments.py (restart step 7) — the weekly-assessment upsert for
#     ``WeeklyAssessment`` after the view has resolved the engagement through
#     scope.advisor_engagement.
#   • calls.py (restart step 10) — the call-log upsert/list materializer for
#     ``WeeklyCallLog`` after the view has resolved the engagement through
#     scope.advisor_engagement.
#   • exam_records.py (restart steps 5+6) — create/update/delete for
#     ``StudyExamScore`` and set-replace for ``StudyExamAnalysis`` (+ rows/
#     notes) after the view has resolved the engagement through
#     scope.advisor_engagement.
#   • monthly.py (restart step 8) — get-or-init + set-replace for
#     ``MonthlyOutlook`` (+ entries/strategies) after the view has resolved
#     the engagement through scope.advisor_engagement or
#     scope.student_active_engagement.
#   • challenges.py (restart step 9) — create/update/delete and the days
#     set-replace for ``StudyChallenge``/``StudyChallengeDay`` after the view
#     has resolved the engagement through scope.advisor_engagement or
#     scope.student_active_engagement.
#   • overview.py (advisor cockpit) — read-only batched metrics for
#     ``GET /api/advisory/overview/``: it aggregates ``DailyLog`` max dates and
#     ACTIVE ``StudyChallenge`` titles across the roster in one query each,
#     while every per-engagement adherence number rides scope.advisor_plans +
#     study_plans.feed_overall_adherence. It writes nothing.
#   • folders.py (risman step 1) — CRUD for advisor-owned student folders and
#     the engagement.folder assignment, after scope resolution.
#   • reports.py (risman step 2) — read-only aggregation engine behind the
#     planner/student/advisor reports (planned-vs-actual, subject share,
#     series). It writes nothing.
#   • excel_export.py (risman step 2) — openpyxl workbook writer consuming the
#     aggregated report dicts; touches no tenancy state itself.
#   • org_overview.py (risman step 3) — org-manager dashboard aggregates and
#     the engagement reassignment mover; every org-scoped query is keyed on the
#     manager's ACTIVE advisory memberships and reassignment revalidates both
#     engagements against that same org before writing.
# The list is pinned by a test below so that a further door cannot appear without
# someone editing this comment.
_EXEMPT_FILES = {
    'scope.py',
    'admin.py',
    'models.py',
    'invites.py',
    'student_subjects.py',
    'daily_logs.py',
    'study_plans.py',
    'intake.py',
    'assessments.py',
    'calls.py',
    'exam_records.py',
    'monthly.py',
    'challenges.py',
    'overview.py',
    'folders.py',
    'reports.py',
    'excel_export.py',
    'org_overview.py',
}


def _is_model_name(name: str) -> bool:
    """``DailyLog`` yes, ``MAX_LOG_NOTE_CHARS`` no.

    Field bounds live in ``models.py`` next to the columns they constrain, and
    importing one carries no tenancy: the serializer needs ``MAX_LOG_NOTE_CHARS`` to
    reject an over-long note, which says nothing about *whose* note it is. Treating
    those as leaks would force every module that validates a length onto the exempt
    list — the opposite of what the list is for.

    Only CapWords names (Django's class convention) count as models; SHOUT_CASE
    constants do not.
    """
    return name[:1].isupper() and not name.isupper()


def _package_of(path: Path) -> str:
    """``…/backend/apps/classes/services/foo.py`` → ``apps.classes.services``."""
    relative = path.relative_to(APPS_DIR.parent)
    return '.'.join(relative.parts[:-1])


def _module_targets(path: Path) -> list[tuple[str, list[str]]]:
    """Return ``(absolute module, [imported names])`` for every import in a file.

    Relative imports are resolved against *this file's* package. Resolving them
    against a fixed prefix instead would make every app's own ``from .models
    import X`` look like an advisory import — a guard that fails on everything is
    as useless as one that fails on nothing.
    """
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    package = _package_of(path)
    found: list[tuple[str, list[str]]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.append((alias.name, []))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ''
            if node.level:
                base = package.split('.')
                trimmed = base[: len(base) - (node.level - 1)] if node.level > 1 else base
                module = '.'.join([*trimmed, module]) if module else '.'.join(trimmed)
            found.append((module, [a.name for a in node.names]))
    return found


def _python_files(root: Path):
    for path in sorted(root.rglob('*.py')):
        if '__pycache__' in path.parts:
            continue
        yield path


# ── 1. classes must not depend on advisory ───────────────────────────────────

def test_classes_never_imports_advisory():
    offenders = [
        str(path.relative_to(APPS_DIR))
        for path in _python_files(CLASSES_DIR)
        for module, _names in _module_targets(path)
        if module == 'apps.advisory' or module.startswith('apps.advisory.')
    ]
    assert offenders == [], (
        'apps.classes must not import apps.advisory — the dependency is one-way. '
        f'Offending files: {offenders}'
    )


def test_no_other_app_reaches_into_advisory_internals():
    """Outside apps may use the advisory *API* (urls/views), never its models."""
    offenders = []
    for app_dir in sorted(p for p in APPS_DIR.iterdir() if p.is_dir()):
        if app_dir.name in {'advisory', '__pycache__'}:
            continue
        for path in _python_files(app_dir):
            for module, names in _module_targets(path):
                if module != 'apps.advisory.models':
                    continue
                leaked = {n for n in names if _is_model_name(n)} - _UNSCOPED
                if leaked:
                    offenders.append(f'{path.relative_to(APPS_DIR)} → {sorted(leaked)}')
    assert offenders == [], (
        'Tenancy-bearing advisory models must not be imported outside apps.advisory: '
        f'{offenders}'
    )


# ── 2. inside advisory, models go through scope.py ───────────────────────────

def test_only_scope_imports_tenancy_bearing_models():
    offenders = []
    for path in _python_files(ADVISORY_DIR):
        if path.name in _EXEMPT_FILES or path.name.startswith('test_'):
            continue
        if 'migrations' in path.parts:
            continue
        for module, names in _module_targets(path):
            if module not in {'apps.advisory.models', 'apps.advisory'}:
                continue
            leaked = {n for n in names if n != 'models' and _is_model_name(n)} - _UNSCOPED
            if leaked:
                offenders.append(f'{path.relative_to(ADVISORY_DIR)} → {sorted(leaked)}')
    assert offenders == [], (
        'Only apps/advisory/services/scope.py may import tenancy-bearing advisory '
        f'models; route reads through it instead. Offenders: {offenders}'
    )


def test_the_guard_can_actually_see_advisory_files():
    """A guard that silently walks an empty tree passes forever. Pin the premise."""
    names = {p.name for p in _python_files(ADVISORY_DIR)}
    assert {'models.py', 'views.py', 'urls.py'} <= names
    assert (ADVISORY_DIR / 'services' / 'scope.py').exists()


def test_relative_imports_resolve_against_their_own_package(tmp_path):
    """The resolver is the load-bearing half of both guards above.

    ``from .models import X`` inside ``apps/classes/services/`` must resolve to
    ``apps.classes.services.models`` — never to advisory's. A resolver that got
    this wrong once made both guards fail on every app in the repo.
    """
    target = APPS_DIR / 'classes' / 'services' / '_guard_probe.py'
    target.write_text(
        'from .models import Thing\n'
        'from ..models import Other\n'
        'from apps.advisory.models import Subject\n',
        encoding='utf-8',
    )
    try:
        resolved = dict(_module_targets(target))
    finally:
        target.unlink()

    assert 'apps.classes.services.models' in resolved
    assert 'apps.classes.models' in resolved
    assert resolved['apps.advisory.models'] == ['Subject']


def test_the_guard_would_catch_a_real_violation():
    """Feed the detector a known-bad import list and prove it flags it."""
    bad = [('apps.advisory.models', ['AdvisoryEngagement'])]
    leaked = {n for _module, names in bad for n in names if _is_model_name(n)} - _UNSCOPED
    assert leaked == {'AdvisoryEngagement'}


def test_a_field_bound_constant_is_not_treated_as_a_model():
    """The escape hatch that keeps the exempt list from swallowing serializers.py.

    If this predicate ever flips, every module importing a ``MAX_*`` bound gets
    flagged and the natural fix — appending it to ``_EXEMPT_FILES`` — would quietly
    grant it permission to import ``DailyLog`` too.
    """
    assert _is_model_name('DailyLog')
    assert _is_model_name('StudentSubject')
    assert not _is_model_name('MAX_LOG_NOTE_CHARS')
    assert not _is_model_name('MOOD_MAX')


def test_scope_is_the_only_place_that_knows_the_org_gate():
    """The three visibility conditions live in one function, not in views."""
    source = (ADVISORY_DIR / 'services' / 'scope.py').read_text(encoding='utf-8')
    assert 'OrgRole.ADVISOR' in source
    assert 'MemberStatus.ACTIVE' in source
    assert 'subscription_status' in source


def test_the_exempt_list_does_not_grow_by_accident():
    """Pin the set of files allowed to import a tenancy-bearing model.

    Every entry costs something: it is one more place a future reader has to check
    when asking "who can read another student's log?". Adding one should require
    editing this assertion and the comment above ``_EXEMPT_FILES``, not just
    appending a filename and watching the suite stay green.
    """
    assert _EXEMPT_FILES == {
        'scope.py',
        'admin.py',
        'models.py',
        'invites.py',
        'student_subjects.py',
        'daily_logs.py',
        'study_plans.py',
        'intake.py',
        'assessments.py',
        'calls.py',
        'exam_records.py',
        'monthly.py',
        'challenges.py',
        'overview.py',
        'folders.py',
        'reports.py',
        'excel_export.py',
        'org_overview.py',
    }


def test_views_do_not_import_engagement_directly():
    """The narrow version of the rule above, stated where it actually bites.

    ``views.py`` is where a "just this once" direct query gets written, and a
    direct ``AdvisoryEngagement.objects.filter(advisor=request.user)`` looks
    correct while skipping the organization gate entirely.
    """
    source = (ADVISORY_DIR / 'views.py').read_text(encoding='utf-8')
    assert 'AdvisoryEngagement' not in source, (
        'views.py must go through services/scope.py, not touch the model directly.'
    )

