"""Root conftest for the backend test suite.

Provides (a) the autouse throttle-disable, and (b) the shared fixture layer
(role-authed API clients, a mock-LLM seam, a Tehran time-freeze) built on the
model-bakery recipes in ``testing/recipes.py``. Program: ADR-0003 (docs/testing/).

Recipes are imported lazily INSIDE fixtures so conftest import never touches the
app registry before Django is configured.
"""
import pytest


@pytest.fixture(autouse=True)
def _disable_throttling(settings):
    """Disable DRF throttling for every test."""
    rf = {**settings.REST_FRAMEWORK}
    rf["DEFAULT_THROTTLE_CLASSES"] = []
    rf["DEFAULT_THROTTLE_RATES"] = {}
    settings.REST_FRAMEWORK = rf

    # Clear throttle cache to prevent stale rate-limit data.
    try:
        from django.core.cache import cache
        cache.clear()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Users by role (persisted; each has a unique username / valid phone)
# ---------------------------------------------------------------------------
@pytest.fixture
def admin_user(db):
    from testing.recipes import admin_user as _r
    return _r.make()


@pytest.fixture
def teacher_user(db):
    from testing.recipes import teacher_user as _r
    return _r.make()


@pytest.fixture
def manager_user(db):
    from testing.recipes import manager_user as _r
    return _r.make()


@pytest.fixture
def student_user(db):
    """An onboarded student (completed profile, unique valid phone)."""
    from testing.recipes import student_completed as _r
    return _r.make()


@pytest.fixture
def student_shell(db):
    """A passwordless, pre-onboarding student shell (is_profile_completed=False)."""
    from testing.recipes import student_shell as _r
    return _r.make()


# ---------------------------------------------------------------------------
# Role-authed API clients (force_authenticate — fast; the JWT path is covered
# separately in apps/authentication). Anonymous + wrong-owner legs included.
# ---------------------------------------------------------------------------
def _authed(user):
    from rest_framework.test import APIClient
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def anon_client():
    from rest_framework.test import APIClient
    return APIClient()


@pytest.fixture
def admin_client(admin_user):
    return _authed(admin_user)


@pytest.fixture
def teacher_client(teacher_user):
    return _authed(teacher_user)


@pytest.fixture
def manager_client(manager_user):
    return _authed(manager_user)


@pytest.fixture
def student_client(student_user):
    return _authed(student_user)


@pytest.fixture
def other_teacher_client(db):
    """A second, different teacher — the 'wrong-owner' leg of the matrix."""
    from testing.recipes import teacher_user as _r
    return _authed(_r.make())


@pytest.fixture
def other_student_client(db):
    """A second, different student — the 'other-student' leg of the matrix."""
    from testing.recipes import student_completed as _r
    return _authed(_r.make())


# ---------------------------------------------------------------------------
# LLM mock — patches the module-bound `generate_text` in every pipeline stage so
# no test ever hits the gateway (zero tokens). Opt-in: request `mock_llm`, then
# set `mock_llm.return_value = SimpleNamespace(text=<canned JSON>)` and assert on
# `mock_llm.call_count` / `call_args_list`.
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_llm():
    from types import SimpleNamespace
    from unittest.mock import patch, MagicMock

    targets = [
        'apps.classes.services.transcription.generate_text',
        'apps.classes.services.structure.generate_text',
        'apps.classes.services.prerequisites.generate_text',
        'apps.classes.services.recap.generate_text',
        'apps.classes.services.quizzes.generate_text',
        'apps.classes.services.exam_prep_structure.generate_text',
        'apps.classes.services.pdf_extraction.generate_text',
        'apps.chatbot.services.memory_service.generate_text',
    ]
    mock = MagicMock(
        return_value=SimpleNamespace(text='{}', provider='test', model='test-model')
    )
    started = []
    for target in targets:
        try:
            p = patch(target, mock)
            p.start()
            started.append(p)
        except (AttributeError, ImportError, ModuleNotFoundError):
            continue
    try:
        yield mock
    finally:
        for p in started:
            p.stop()


# ---------------------------------------------------------------------------
# Time freeze at the Asia/Tehran day boundary (UTC+3:30) — for analytics/tz
# bucketing tests. 20:30 UTC == 00:00 the NEXT day in Tehran.
# ---------------------------------------------------------------------------
@pytest.fixture
def freeze_tehran():
    from freezegun import freeze_time
    with freeze_time('2026-06-15 20:30:00'):
        yield
