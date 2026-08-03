import io
import json
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from pypdf import PdfWriter


pytestmark = pytest.mark.django_db


def _pdf(path: Path):
    writer = PdfWriter()
    for _ in range(3):
        writer.add_blank_page(width=480, height=680)
    output = io.BytesIO()
    writer.write(output)
    path.write_bytes(output.getvalue())
    return path


def _fixture(fixture_id, path, pattern, roles):
    return {
        'fixtureId': fixture_id,
        'pattern': pattern,
        'pdfPath': str(path),
        'expectedPageCount': 3,
        'expectedSegments': [
            {'startPage': index, 'endPage': index, 'role': role}
            for index, role in enumerate(roles, start=1)
        ],
    }


def test_command_rejects_filename_like_fixture_id_without_echoing_it(
    tmp_path,
    settings,
):
    settings.EXAM_PREP_V4_ENABLED = True
    paths = [_pdf(tmp_path / f'private-{index}.pdf') for index in range(3)]
    private_identifier = 'teacher-secret-source.pdf'
    manifest = {
        'manifestVersion': 1,
        'fixtures': [
            _fixture(
                private_identifier,
                paths[0],
                'cover_questions_solutions',
                ['cover', 'questions', 'answer_solutions'],
            ),
            _fixture(
                'fixture-b',
                paths[1],
                'solutions_cover_questions',
                ['answer_solutions', 'cover', 'questions'],
            ),
            _fixture(
                'fixture-c',
                paths[2],
                'cover_questions_solutions_overlap',
                ['cover', 'questions', 'answer_solutions'],
            ),
        ],
    }
    manifest_path = tmp_path / 'manifest.json'
    manifest_path.write_text(json.dumps(manifest), encoding='utf-8')

    with pytest.raises(CommandError) as caught:
        call_command(
            'benchmark_exam_prep_v4',
            manifest=str(manifest_path),
            fake_provider=True,
        )

    message = str(caught.value)
    assert 'anonymous lowercase identifiers' in message
    assert private_identifier not in message
    assert all(path.name not in message for path in paths)
    assert all(str(path) not in message for path in paths)
