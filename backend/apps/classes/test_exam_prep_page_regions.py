import io

import pytest
from PIL import Image

from apps.classes.services.exam_prep_page_records import (
    PageExtraction,
    PageRecord,
)
from apps.classes.services.exam_prep_page_regions import (
    merge_page_region_extractions,
    split_vertical_columns,
)


pytestmark = pytest.mark.unit


def _png(width=1000, height=600):
    image = Image.new('RGB', (width, height), 'white')
    output = io.BytesIO()
    image.save(output, format='PNG')
    image.close()
    return output.getvalue()


def test_columns_are_returned_in_persian_reading_order():
    right, left = split_vertical_columns(
        _png(),
        right_native_text='متن ستون راست',
        left_native_text='متن ستون چپ',
    )

    assert right.region == 'right_column'
    assert right.reading_order == 0
    assert right.native_text == 'متن ستون راست'
    assert left.region == 'left_column'
    assert left.reading_order == 1
    assert left.native_text == 'متن ستون چپ'
    assert right.image.startswith(b'\x89PNG')
    assert left.image.startswith(b'\x89PNG')


def test_column_solution_replaces_short_full_page_answer():
    full = PageExtraction(
        page_number=10,
        records=[
            PageRecord(
                question_number=9,
                record_type='answer',
                correct_option_label='4',
                confidence=0.7,
            )
        ],
    )
    right = PageExtraction(
        page_number=10,
        records=[
            PageRecord(
                question_number=9,
                record_type='solution',
                correct_option_label='4',
                teacher_solution_markdown='راه‌حل تشریحی کامل سؤال ۹',
                confidence=0.95,
            )
        ],
    )

    merged = merge_page_region_extractions(full, [right])

    assert len(merged.records) == 1
    record = merged.records[0]
    assert record.record_type == 'solution'
    assert record.correct_option_label == '4'
    assert record.teacher_solution_markdown == 'راه‌حل تشریحی کامل سؤال ۹'
