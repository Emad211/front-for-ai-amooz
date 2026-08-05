import pytest

from apps.classes.services.exam_prep_page_regions import merge_page_region_extractions
from apps.classes.services.exam_prep_page_source import (
    SourceBBox,
    SourcePageExtraction,
    SourcePageRecord,
)


pytestmark = pytest.mark.unit


def test_region_merge_prefers_tight_complete_bbox():
    full_page = SourcePageExtraction(
        page_number=10,
        records=[
            SourcePageRecord(
                question_number=18,
                record_type='solution',
                source_bbox=SourceBBox(x0=0.05, y0=0.05, x1=0.95, y1=0.95),
                correct_option_label='3',
                teacher_solution_markdown='راه حل کوتاه',
                confidence=0.7,
            )
        ],
    )
    column = SourcePageExtraction(
        page_number=10,
        records=[
            SourcePageRecord(
                question_number=18,
                record_type='solution',
                source_bbox=SourceBBox(x0=0.52, y0=0.20, x1=0.96, y1=0.55),
                correct_option_label='3',
                teacher_solution_markdown='راه حل تشریحی کامل و دقیق سؤال',
                confidence=0.95,
            )
        ],
    )

    merged = merge_page_region_extractions(full_page, [column])
    bbox = merged.records[0].source_bbox

    assert bbox is not None
    assert bbox.model_dump() == {
        'x0': 0.52,
        'y0': 0.20,
        'x1': 0.96,
        'y1': 0.55,
    }
