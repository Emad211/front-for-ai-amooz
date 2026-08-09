from __future__ import annotations

from apps.classes.management.commands.capture_exam_prep_mistral_ocr4_bundle import (
    _LocalOCRCheckpointStore,
)
from apps.classes.services.exam_prep_mistral_ocr_transport import OCR4Chunk


def _chunk() -> OCR4Chunk:
    return OCR4Chunk(
        index=0,
        physical_pages=tuple(range(1, 31)),
        data=b"pdf",
        sha256="c" * 64,
    )


def test_local_capture_checkpoint_roundtrip_is_storage_independent(tmp_path):
    store = _LocalOCRCheckpointStore(tmp_path / "capture.zip.checkpoints")
    kwargs = {
        "source_sha256": "s" * 64,
        "contract_fingerprint": "f" * 64,
        "chunk": _chunk(),
    }
    store.save(**kwargs, payload=b"validated-provider-payload")
    assert store.load(**kwargs) == b"validated-provider-payload"
    store.delete(**kwargs)
    assert store.load(**kwargs) is None


def test_local_capture_checkpoint_path_uses_short_windows_safe_components(tmp_path):
    store = _LocalOCRCheckpointStore(tmp_path / "capture.zip.checkpoints")
    path = store._path(
        source_sha256="s" * 64,
        contract_fingerprint="f" * 64,
        chunk=_chunk(),
    )
    assert path.parent.name == "f" * 12
    assert path.parent.parent.name == "s" * 12
    assert path.name == "c000-cccccccccc.json"
