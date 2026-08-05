import pytest

from apps.classes.services.exam_prep_page_records import (
    PageOption,
    assemble_page_extractions,
)
from apps.classes.services.exam_prep_page_source import (
    SourceBBox,
    SourcePageExtraction,
    SourcePageRecord,
    attach_source_regions,
    remap_extraction_bboxes,
)


pytestmark = pytest.mark.unit


def test_bbox_accepts_list_and_rejects_negative_area():
    bbox = SourceBBox.model_validate([0.1, 0.2, 0.8, 0.9])
    assert bbox.model_dump() == {'x0': 0.1, 'y0': 0.2, 'x1': 0.8, 'y1': 0.9}

    with pytest.raises(ValueError):
        SourceBBox(x0=0.8, y0=0.2, x1=0.1, y1=0.9)


def test_column_bbox_maps_back_to_full_page():
    page = SourcePageExtraction(
        page_number=10,
        records=[
            SourcePageRecord(
                question_number=18,
                record_type='solution',
                source_bbox=SourceBBox(x0=0.1, y0=0.2, x1=0.9, y1=0.8),
                correct_option_label='3',
                teacher_solution_markdown='راه حل کامل',
                confidence=0.9,
            )
        ],
    )

    remapped = remap_extraction_bboxes(page, region_x0=0.5, region_x1=1.0)
    bbox = remapped.records[0].source_bbox
    assert bbox is not None
    assert bbox.x0 == pytest.approx(0.55)
    assert bbox.x1 == pytest.approx(0.95)
    assert bbox.y0 == pytest.approx(0.2)
    assert bbox.y1 == pytest.approx(0.8)


def test_assembled_question_keeps_separate_question_and_answer_regions():
    question_page = SourcePageExtraction(
        page_number=4,
        records=[
            SourcePageRecord(
                question_number=18,
                record_type='question',
                source_bbox=SourceBBox(x0=0.05, y0=0.1, x1=0.95, y1=0.5),
                question_text_markdown='کدام گزینه درست است؟',
                options=[
                    PageOption(label='1', text_markdown='اول'),
                    PageOption(label='2', text_markdown='دوم'),
                ],
                confidence=0.9,
            )
        ],
    )
    answer_page = SourcePageExtraction(
        page_number=11,
        records=[
            SourcePageRecord(
                question_number=18,
                record_type='solution',
                source_bbox=SourceBBox(x0=0.5, y0=0.2, x1=0.98, y1=0.7),
                correct_option_label='2',
                teacher_solution_markdown='راه حل تشریحی کامل',
                confidence=0.9,
            )
        ],
    )

    result = assemble_page_extractions([question_page, answer_page])
    result = attach_source_regions(result, pages=[question_page, answer_page])
    regions = result.projection['exam_prep']['questions'][0]['source_regions']

    assert [(item['page_number'], item['role']) for item in regions] == [
        (4, 'question'),
        (11, 'answer'),
    ]
    assert regions[0]['bbox']['x0'] == 0.05
    assert regions[1]['bbox']['x0'] == 0.5
