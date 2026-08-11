from __future__ import annotations

import hashlib
import io

from apps.classes import views_exam_prep_inline_visual as view
from apps.classes.services import exam_prep_mistral_visuals as visuals


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
    source_sha256 = "a" * 64
    name = f"exam-prep/source/visuals/v1/{source_sha256}/q001-question.png"
    monkeypatch.setattr(view, "storages", _Storages(_Storage({name: payload})))
    assert view._stored_source_visual(
        {
            "storagePath": name,
            "contentType": "image/png",
            "byteSize": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "sourceSha256": source_sha256,
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
    source_sha256 = "b" * 64
    name = f"exam-prep/source/visuals/v1/{source_sha256}/q001-question.png"
    monkeypatch.setattr(view, "storages", _Storages(_Storage({name: payload})))
    assert view._stored_source_visual(
        {
            "storagePath": name,
            "contentType": "image/png",
            "byteSize": len(payload) + 1,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "sourceSha256": source_sha256,
        }
    ) is None


def test_stage3_storage_path_rejects_wrong_source_namespace_and_payload_hash(monkeypatch):
    payload = b"trusted"
    source_sha256 = "c" * 64
    wrong_source_sha256 = "d" * 64
    wrong_name = (
        f"exam-prep/source/visuals/v1/{wrong_source_sha256}/q001-question.png"
    )
    monkeypatch.setattr(
        view,
        "storages",
        _Storages(_Storage({wrong_name: payload})),
    )

    common = {
        "storagePath": wrong_name,
        "contentType": "image/png",
        "byteSize": len(payload),
        "sourceSha256": source_sha256,
    }
    assert view._stored_source_visual(
        {**common, "sha256": hashlib.sha256(payload).hexdigest()}
    ) is None

    correct_name = f"exam-prep/source/visuals/v1/{source_sha256}/q001-question.png"
    monkeypatch.setattr(
        view,
        "storages",
        _Storages(_Storage({correct_name: payload})),
    )
    assert view._stored_source_visual(
        {
            **common,
            "storagePath": correct_name,
            "sha256": "e" * 64,
        }
    ) is None


def test_visual_asset_registry_freezes_only_valid_stage3_assets():
    source_sha256 = "f" * 64
    payload_sha256 = "1" * 64
    valid_path = (
        f"exam-prep/source/visuals/v1/{source_sha256}/p001-q001-question.png"
    )
    projection = {
        "exam_prep": {
            "questions": [
                {
                    "question_id": "q-1",
                    "visuals": [
                        {
                            "id": "visual-1",
                            "role": "question",
                            "optionLabel": None,
                            "storagePath": valid_path,
                            "contentType": "image/png",
                            "byteSize": 17,
                            "sha256": payload_sha256,
                        },
                        {
                            "id": "bad-path",
                            "role": "question",
                            "storagePath": "exam-prep/source/visuals/v1/other/a.png",
                            "contentType": "image/png",
                            "byteSize": 12,
                            "sha256": "2" * 64,
                        },
                    ],
                }
            ]
        }
    }

    registry = visuals.build_visual_asset_registry(
        projection,
        source_sha256=source_sha256,
    )

    assert registry == {
        "visual-1": {
            "id": "visual-1",
            "questionId": "q-1",
            "role": "question",
            "optionLabel": None,
            "storagePath": valid_path,
            "contentType": "image/png",
            "byteSize": 17,
            "sha256": payload_sha256,
            "sourceSha256": source_sha256,
        }
    }
