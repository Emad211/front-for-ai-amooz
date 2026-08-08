import io

import pytest
from django.core.management.base import CommandError
from pypdf import PdfReader, PdfWriter

from apps.classes.management.commands.probe_exam_prep_mistral_chunked_document import (
    _plan_chunks,
)


def _pdf(path, pages):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    with path.open("wb") as handle:
        writer.write(handle)


def test_plan_chunks_uses_minimum_two_requests_for_55_pages(tmp_path):
    path = tmp_path / "exam.pdf"
    _pdf(path, 55)

    chunks = _plan_chunks(
        path,
        page_count=55,
        max_pages=30,
        max_bytes=10 * 1024 * 1024,
    )

    assert [len(pages) for pages, _data in chunks] == [30, 25]
    assert chunks[0][0] == tuple(range(1, 31))
    assert chunks[1][0] == tuple(range(31, 56))
    assert [
        len(PdfReader(io.BytesIO(data)).pages)
        for _pages, data in chunks
    ] == [30, 25]


def test_plan_chunks_fails_before_network_when_one_page_exceeds_byte_cap(tmp_path):
    path = tmp_path / "exam.pdf"
    _pdf(path, 1)

    with pytest.raises(CommandError, match="Physical page 1 alone"):
        _plan_chunks(
            path,
            page_count=1,
            max_pages=30,
            max_bytes=10,
        )
