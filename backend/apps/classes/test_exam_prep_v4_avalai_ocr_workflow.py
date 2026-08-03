from pathlib import Path


WORKFLOW_PATH = (
    Path(__file__).resolve().parents[3]
    / '.github'
    / 'workflows'
    / 'exam-prep-v4-avalai-ocr-live-smoke.yml'
)


def _workflow_text() -> str:
    return WORKFLOW_PATH.read_text(encoding='utf-8')


def test_live_ocr_workflow_is_manual_only_and_read_only():
    text = _workflow_text()

    assert 'workflow_dispatch:' in text
    assert 'pull_request:' not in text
    assert 'push:' not in text
    assert 'schedule:' not in text
    assert 'contents: read' in text
    assert 'I_APPROVE_8_PRIVATE_OCR_REQUESTS' in text
    assert 'feat/exam-prep-v4-source-aware' in text


def test_live_ocr_workflow_uses_only_named_secrets_and_pinned_model():
    text = _workflow_text()

    assert '${{ secrets.AVALAI_API_KEY }}' in text
    assert '${{ secrets.OCR_QUESTION_PAGE_URL }}' in text
    assert '${{ secrets.OCR_ANSWER_PAGE_URL }}' in text
    assert '--model mistral-ocr-4-0' in text
    assert '--max-requests 8' in text
    assert '--allow-private-transmission' in text
    assert '--smoke-modes markdown,blocks,document_annotation,bbox_annotation' in text


def test_live_ocr_workflow_never_uploads_private_inputs():
    text = _workflow_text()

    assert 'aggregate-report.json' in text
    assert 'retention-days: 1' in text
    assert 'name: exam-prep-v4-avalai-ocr-aggregate' in text
    assert 'path: ${{ runner.temp }}/exam-prep-v4-ocr-smoke/aggregate-report.json' in text
    assert 'path: ${{ runner.temp }}/exam-prep-v4-ocr-smoke' not in text
    assert 'include_image_base64' not in text
    assert 'shred -u' in text
    assert 'rm -rf "${PRIVATE_DIR}"' in text


def test_live_ocr_workflow_bounds_and_validates_private_downloads():
    text = _workflow_text()

    assert 'max_bytes = 12 * 1024 * 1024' in text
    assert "raw.startswith(b'\\x89PNG\\r\\n\\x1a\\n')" in text
    assert "raw.startswith(b'\\xff\\xd8\\xff')" in text
    assert 'private smoke inputs must be different images' in text
    assert "assert report['executedRequestCount'] == 8" in text
    assert "assert report['acceptance']['passed'] is True" in text
