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


def test_live_ocr_workflow_uses_only_api_secret_and_pinned_model():
    text = _workflow_text()

    assert '${{ secrets.AVALAI_API_KEY }}' in text
    assert 'OCR_QUESTION_PAGE_URL' not in text
    assert 'OCR_ANSWER_PAGE_URL' not in text
    assert '--model mistral-ocr-4-0' in text
    assert '--max-requests 8' in text
    assert '--allow-private-transmission' in text
    assert '--smoke-modes markdown,blocks,document_annotation,bbox_annotation' in text


def test_live_ocr_workflow_extracts_only_selected_main_pages():
    text = _workflow_text()

    assert "SOURCE_PDF_REPO_PATH: 'دفترچه اول (زیست).pdf'" in text
    assert "EXPECTED_PAGE_COUNT: '16'" in text
    assert "QUESTION_PAGE_NUMBER: '5'" in text
    assert "ANSWER_PAGE_NUMBER: '12'" in text
    assert 'git fetch --no-tags --depth=1 origin main' in text
    assert 'git show "origin/main:${SOURCE_PDF_REPO_PATH}"' in text
    assert "source_path.read_bytes()[:5] != b'%PDF-'" in text
    assert 'pypdfium2 as pdfium' in text
    assert "if len(document) != expected_page_count" in text
    assert 'page.render(scale=2.0)' in text
    assert 'image.thumbnail((1800, 2400))' in text
    assert '12 * 1024 * 1024' in text
    assert 'selected smoke pages must be different images' in text
    assert 'shred -u "${PRIVATE_DIR}/source.pdf"' in text


def test_live_ocr_workflow_uses_valid_temp_paths_and_never_uploads_private_inputs():
    text = _workflow_text()

    assert 'PRIVATE_DIR: /tmp/exam-prep-v4-ocr-smoke' in text
    assert 'REPORT_PATH: /tmp/exam-prep-v4-ocr-smoke/aggregate-report.json' in text
    assert '${{ runner.temp }}' not in text
    assert 'path: ${{ env.REPORT_PATH }}' in text
    assert 'retention-days: 1' in text
    assert 'name: exam-prep-v4-avalai-ocr-aggregate' in text
    assert 'include_image_base64' not in text
    assert 'find "${PRIVATE_DIR}" -type f -exec shred -u {}' in text
    assert 'rm -rf "${PRIVATE_DIR}"' in text
    assert "assert report['executedRequestCount'] == 8" in text
    assert "assert report['acceptance']['passed'] is True" in text
