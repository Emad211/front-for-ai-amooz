from __future__ import annotations

import json
from pathlib import Path
import zipfile

import pytest
from django.core.management.base import CommandError

from apps.classes.management.commands.replay_exam_prep_mistral_visual_stage3 import (
    _DiagnosticStore,
    _load_bundle_root,
    _physical_pages,
)


def _zip(path: Path, files: dict[str, object]) -> Path:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, value in files.items():
            if isinstance(value, bytes):
                payload = value
            else:
                payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
            archive.writestr(name, payload)
    return path


def test_success_bundle_loader_finds_merged_response_inside_zip(tmp_path):
    path = _zip(
        tmp_path / "bundle.zip",
        {
            "nested/response.raw.json": {
                "pages": [{"index": 0, "blocks": []}],
                "model": "mistral-ocr-4-0",
            },
            "manifest.json": {"pageCount": 1},
        },
    )
    root, manifest = _load_bundle_root(path)
    assert root["model"] == "mistral-ocr-4-0"
    assert manifest["pageCount"] == 1


def test_failure_bundle_without_merged_response_is_rejected(tmp_path):
    path = _zip(
        tmp_path / "failure.zip",
        {"failure.json": {"failed": True, "httpStatus": 502}},
    )
    with pytest.raises(CommandError, match="response.raw.json"):
        _load_bundle_root(path)


def test_replay_requires_exact_one_based_physical_page_coverage():
    pages = _physical_pages(
        {
            "pages": [
                {"index": 0, "blocks": []},
                {"index": 1, "blocks": []},
            ]
        },
        page_count=2,
    )
    assert [item["sourcePhysicalPage"] for item in pages] == [1, 2]

    with pytest.raises(CommandError, match="exactly cover"):
        _physical_pages(
            {"pages": [{"index": 0, "blocks": []}]},
            page_count=2,
        )


def test_diagnostic_store_preserves_private_storage_identity_locally(tmp_path):
    store = _DiagnosticStore(tmp_path)
    name = "exam-prep/source/visuals/v1/source/p001-q001-question-01-a.png"
    assert store.save(name, b"png") == name
    relative = store.files[name]
    assert relative.startswith("assets/")
    assert relative.endswith(".png")
    assert (tmp_path / relative).read_bytes() == b"png"


def test_diagnostic_store_rejects_path_traversal(tmp_path):
    store = _DiagnosticStore(tmp_path)
    with pytest.raises(ValueError, match="Unsafe"):
        store.save("../outside.png", b"x")
