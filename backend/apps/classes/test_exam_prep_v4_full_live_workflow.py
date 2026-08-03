from pathlib import Path


WORKFLOW_PATH = (
    Path(__file__).resolve().parents[3]
    / '.github'
    / 'workflows'
    / 'exam-prep-v4-full-live-benchmark.yml'
)


def _workflow() -> str:
    return WORKFLOW_PATH.read_text(encoding='utf-8')


def test_full_live_workflow_is_manual_only_and_has_no_confirmation_input():
    text = _workflow()

    assert 'workflow_dispatch:' in text
    assert 'push:' not in text
    assert 'pull_request:' not in text
    assert 'schedule:' not in text
    assert 'inputs:' not in text
    assert 'contents: read' in text
    assert 'cancel-in-progress: false' in text


def test_full_live_workflow_uses_exact_fixtures_models_and_ceiling():
    text = _workflow()

    assert 'دفترچه اول (زیست).pdf' in text
    assert 'دفترچه دوم .pdf' in text
    assert 'دفترچه سوم.pdf' in text
    assert '--classifier-model gemini-2.5-flash' in text
    assert '--block-model gemini-2.5-flash' in text
    assert '--question-model gemini-2.5-flash' in text
    assert '--answer-model gemini-2.5-flash' in text
    assert '--ocr-model mistral-ocr-4-0' in text
    assert '--ocr-max-attempts 2' in text
    assert '--ocr-bbox-for-diagrams' in text
    assert '--max-provider-calls 484' in text
    assert "assert plan['requiredMinimum'] == 484" in text
    assert "assert plan['ocrEligiblePageCount'] == 55" in text


def test_full_live_workflow_preserves_only_aggregate_or_safe_failure_summary():
    text = _workflow()

    assert 'exam-prep-v4-full-live-aggregate' in text
    assert 'path: ${{ env.ARTIFACT_PATH }}' in text
    assert 'retention-days: 1' in text
    assert "'reportAvailable': False" in text
    assert 'issues/4/comments' not in text
    assert 'GH_TOKEN' not in text
    assert 'find "${PRIVATE_DIR}" -type f -exec shred -u {}' in text
    assert 'rm -rf "${GITHUB_WORKSPACE}/fixtures"' in text


def test_full_live_workflow_never_retries_automatically():
    text = _workflow()

    assert 'rerun' not in text.lower()
    assert 'retry' not in text.lower()
    assert 'max-attempts 2' in text
    assert 'Fail when benchmark command failed' in text
