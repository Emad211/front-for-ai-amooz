from __future__ import annotations

import io

from apps.classes import views_exam_prep_inline_visual as view


class _Storage:
    def __init__(self, files: dict[str, bytes]):
        self.files = files

    def open(self, name: str, mode: str):
        assert mode == "rb"
        return io.BytesIO(self.files[name])


class _Storages:
    def __init__(self, storage):
        self.storage = storage

    def __getitem__(self, key: str):
        assert key == "answer_sources"
        return self.storage


def test_stage3_storage_path_is_read_only_from_private_visual_namespace(monkeypatch):
    payload = b"\x89PNG\r\nvisual"
    name = "exam-prep/source/visuals/v1/source/q001-question-01-deadbeef.png"
    monkeypatch.setattr(view, "storages", _Storages(_Storage({name: payload})))
    assert view._stored_source_visual(
        {
            "storagePath": name,
            "contentType": "image/png",
            "byteSize": len(payload),
        }
    ) == (payload, "image/png")


def test_stage3_storage_path_rejects_traversal_and_wrong_namespace(monkeypatch):
    monkeypatch.setattr(view, "storages", _Storages(_Storage({})))
    assert view._stored_source_visual(
        {
            "storagePath": "exam-prep/source/visuals/v1/../secret.png",
            "contentType": "image/png",
        }
    ) is None
    assert view._stored_source_visual(
        {
            "storagePath": "class_creation/source/private.png",
            "contentType": "image/png",
        }
    ) is None


def test_stage3_storage_path_rejects_declared_size_mismatch(monkeypatch):
    payload = b"small"
    name = "exam-prep/source/visuals/v1/source/q001-question-01-deadbeef.png"
    monkeypatch.setattr(view, "storages", _Storages(_Storage({name: payload})))
    assert view._stored_source_visual(
        {
            "storagePath": name,
            "contentType": "image/png",
            "byteSize": len(payload) + 1,
        }
    ) is None
