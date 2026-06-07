"""Regression tests for the "new video uploads but pipeline outputs the OLD
video's content" bug.

Root cause: the Step-1 idempotency block returned the existing session and
silently discarded a newly uploaded DIFFERENT file. The fix makes idempotency
content-aware: same file -> dedupe; different file under the same key -> process
the new upload as a fresh session (never return stale output, never drop the file).
"""
import tempfile
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from model_bakery import baker
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.classes.models import ClassCreationSession
from apps.classes.views import _is_same_uploaded_source

pytestmark = pytest.mark.unit


# --------------------------------------------------------------------------
# Pure helper logic
# --------------------------------------------------------------------------

def _fake_session(name, size=None):
    source_file = MagicMock(size=size) if size is not None else None
    return SimpleNamespace(source_original_name=name, source_file=source_file)


def _fake_upload(name, size):
    return SimpleNamespace(name=name, size=size)


def test_same_name_and_size_is_same_source():
    assert _is_same_uploaded_source(_fake_session("a.mp4", 100), _fake_upload("a.mp4", 100)) is True


def test_different_name_is_not_same_source():
    assert _is_same_uploaded_source(_fake_session("a.mp4", 100), _fake_upload("b.mp4", 100)) is False


def test_same_name_different_size_is_not_same_source():
    assert _is_same_uploaded_source(_fake_session("a.mp4", 100), _fake_upload("a.mp4", 999)) is False


def test_deleted_source_file_falls_back_to_name_match():
    # Completed sessions delete source_file but keep source_original_name.
    assert _is_same_uploaded_source(_fake_session("a.mp4", size=None), _fake_upload("a.mp4", 100)) is True
    assert _is_same_uploaded_source(_fake_session("a.mp4", size=None), _fake_upload("b.mp4", 100)) is False


# --------------------------------------------------------------------------
# View integration (in-memory storage; pipeline dispatch mocked)
# --------------------------------------------------------------------------

_STEP1_URL = "/api/classes/creation-sessions/step-1/"

# Local filesystem storage in a temp dir (avoids MinIO/S3 and a Windows-only
# InMemoryStorage temp-file lock); MemoryFileUploadHandler keeps uploads in RAM
# so no TemporaryUploadedFile is created.
_TMP_MEDIA = tempfile.mkdtemp(prefix="aiamooz_test_media_")
_FS_STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {"location": _TMP_MEDIA},
    },
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@override_settings(
    STORAGES=_FS_STORAGES,
    FILE_UPLOAD_HANDLERS=["django.core.files.uploadhandler.MemoryFileUploadHandler"],
    CLASS_PIPELINE_ASYNC=True,
)
@patch("apps.classes.views.process_class_full_pipeline", new=MagicMock())
@patch("apps.classes.views.process_class_step1_transcription", new=MagicMock())
class Step1IdempotencyViewTests(APITestCase):
    def setUp(self):
        self.teacher = baker.make(User, role=User.Role.TEACHER)
        self.client.force_authenticate(user=self.teacher)

    def _post(self, *, name, content, key, title="t"):
        upload = SimpleUploadedFile(name, content, content_type="video/mp4")
        return self.client.post(
            _STEP1_URL,
            {"title": title, "file": upload, "client_request_id": str(key)},
            format="multipart",
        )

    def test_reused_key_with_different_file_creates_new_session(self):
        key = uuid.uuid4()
        r1 = self._post(name="old.mp4", content=b"AAAAAAAA", key=key)
        assert r1.status_code in (200, 202), r1.content
        sid1 = r1.data["id"]

        # Same idempotency key, but a genuinely different file.
        r2 = self._post(name="new.mp4", content=b"BBBBBBBBBBBB", key=key)
        assert r2.status_code in (200, 202), r2.content
        sid2 = r2.data["id"]

        assert sid1 != sid2, "different upload must NOT return the stale session"
        assert ClassCreationSession.objects.filter(teacher=self.teacher).count() == 2

    def test_same_key_same_file_dedupes(self):
        key = uuid.uuid4()
        r1 = self._post(name="same.mp4", content=b"IDENTICALBYTES", key=key)
        r2 = self._post(name="same.mp4", content=b"IDENTICALBYTES", key=key)
        assert r1.data["id"] == r2.data["id"], "a true retry must dedupe to one session"
        assert ClassCreationSession.objects.filter(teacher=self.teacher).count() == 1
