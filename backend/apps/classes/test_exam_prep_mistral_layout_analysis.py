from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageDraw

from apps.classes.services.exam_prep_mistral_layout_analysis import (
    analyze_ocr_document,
    associate_uncovered_graphics,
    detect_uncovered_graphics,
)


def _block(kind, x0, y0, x1, y1, content=''):
    return {
        'type': kind,
        'bbox': {'x0': x0, 'y0': y0, 'x1': x1, 'y1': y1},
        'content': content,
    }


def _page(index, blocks, *, tables=None, confidence=None):
    return {
        'index': index,
        'markdown': '',
        'dimensions': {'width': 1000, 'height': 1400, 'dpi': 200},
        'blocks': blocks,
        'tables': tables or [],
        'confidence_scores': confidence or {
            'average_page_confidence_score': 0.96,
            'minimum_page_confidence_score': 0.90,
        },
    }


def test_rtl_columns_are_reordered_and_compact_solution_numbers_recovered():
    blocks = [
        _block('title', 80, 100, 420, 140, '«55 گزینه 2»'),
        _block('text', 80, 150, 420, 250, 'راه حل'),
        _block('title', 80, 300, 420, 340, '«6 گزینه 4»'),
        _block('text', 80, 350, 420, 450, 'راه حل'),
        _block('title', 80, 500, 420, 540, '«7 گزینه 1»'),
        _block('text', 80, 550, 420, 650, 'راه حل'),
        _block('title', 580, 100, 920, 140, '«51 گزینه 1»'),
        _block('text', 580, 150, 920, 250, 'راه حل'),
        _block('title', 580, 300, 920, 340, '«52 گزینه 2»'),
        _block('text', 580, 350, 920, 450, 'راه حل'),
        _block('title', 580, 500, 920, 540, '«53 گزینه 3»'),
        _block('text', 580, 550, 920, 650, 'راه حل'),
        _block('title', 580, 700, 920, 740, '«54 گزینه 4»'),
        _block('text', 580, 750, 920, 850, 'راه حل'),
    ]
    result = analyze_ocr_document(
        {'model': 'mistral-ocr-4-0', 'pages': [_page(0, blocks)]}
    )
    page = result['pages'][0]
    assert page['rtlDoubleColumn'] is True
    assert [r['questionNumber'] for r in page['regions']] == [
        51, 52, 53, 54, 55, 56, 57
    ]
    assert page['regions'][-2]['rawQuestionNumber'] == 6
    assert page['regions'][-2]['numberRecoveredFromSequence'] is True
    assert page['regions'][-1]['rawQuestionNumber'] == 7
    assert page['regions'][-1]['numberRecoveredFromSequence'] is True
    assert 'provider_reading_order_corrected_for_rtl_columns' in page['issues']


def test_wrapped_solution_heading_keeps_source_geometry_and_content():
    wrapped_heading = r'$$\text{۸۹- گزینه «۳»}$$'
    blocks = [
        _block('title', 100, 100, 900, 140, wrapped_heading),
        _block('text', 100, 150, 900, 250, 'راه حل'),
    ]

    result = analyze_ocr_document(
        {'model': 'mistral-ocr-4-0', 'pages': [_page(0, blocks)]}
    )

    region = result['pages'][0]['regions'][0]
    assert region['kind'] == 'solution'
    assert region['questionNumber'] == 89
    assert region['correctOptionLabel'] == 3
    assert region['headingProviderIndex'] == 0
    assert region['bbox'] == [0.0, 100 / 1400, 1.0, 0.98]
    assert region['contentBBox'] == [0.1, 100 / 1400, 0.9, 250 / 1400]
    assert region['text'].startswith(wrapped_heading)


def test_option_first_solution_heading_is_a_distinct_layout_region():
    blocks = [
        _block('title', 100, 100, 900, 140, '«۴» گزینه - ۱۱۲'),
        _block('text', 100, 150, 900, 250, 'راه حل'),
    ]

    result = analyze_ocr_document(
        {'model': 'mistral-ocr-4-0', 'pages': [_page(0, blocks)]}
    )

    [region] = result['pages'][0]['regions']
    assert region['kind'] == 'solution'
    assert region['questionNumber'] == 112
    assert region['correctOptionLabel'] == 4
    assert region['headingProviderIndex'] == 0


def test_solution_page_does_not_promote_numbered_body_options_to_questions():
    blocks = [
        _block('title', 580, 100, 920, 140, '۱- گزینه ۲'),
        _block('text', 580, 150, 920, 250, 'راه حل یک'),
        _block('text', 580, 300, 920, 340, '۱- مورد فرعی داخل راه حل'),
        _block('title', 580, 500, 920, 540, '۲- گزینه ۳'),
        _block('text', 580, 550, 920, 650, 'راه حل دو'),
    ]

    result = analyze_ocr_document(
        {'model': 'mistral-ocr-4-0', 'pages': [_page(0, blocks)]}
    )

    page = result['pages'][0]
    assert page['pageRole'] == 'solution'
    assert [(region['kind'], region['questionNumber']) for region in page['regions']] == [
        ('solution', 1),
        ('solution', 2),
    ]


def test_caption_count_detects_missing_chemical_structure_block():
    blocks = [
        _block('title', 100, 100, 900, 140, '94- کدام ساختار درست است؟'),
        _block('image', 100, 200, 250, 330),
        _block('caption', 130, 340, 220, 380, '(C)'),
        _block('caption', 450, 340, 540, 380, '(B)'),
        _block('image', 700, 200, 850, 330),
        _block('caption', 730, 340, 820, 380, '(A)'),
    ]
    result = analyze_ocr_document(
        {'model': 'mistral-ocr-4-0', 'pages': [_page(0, blocks)]}
    )
    assert 'caption_visual_count_mismatch' in result['pages'][0]['regions'][0]['issues']


def test_four_visual_options_in_one_image_block_are_flagged():
    blocks = [
        _block(
            'title',
            100,
            100,
            900,
            140,
            '65- کدام یک از گزینه های زیر درست است؟',
        ),
        _block('image', 150, 250, 850, 700),
    ]
    result = analyze_ocr_document(
        {'model': 'mistral-ocr-4-0', 'pages': [_page(0, blocks)]}
    )
    region = result['pages'][0]['regions'][0]
    assert region['visualOptionMode'] == 'grouped_single_block'
    assert 'visual_options_grouped_in_single_block' in region['issues']


def test_table_with_empty_visual_cells_is_flagged_for_source_crop_preservation():
    blocks = [
        _block('title', 100, 100, 900, 140, '81- با توجه به جدول پاسخ دهید'),
        {
            **_block('table', 120, 200, 880, 600, 'table-1'),
            'table_id': 'tbl-1',
        },
    ]
    tables = [
        {'id': 'tbl-1', 'content': '<table><tr><td>ظرف</td><td></td></tr></table>'}
    ]
    result = analyze_ocr_document(
        {'model': 'mistral-ocr-4-0', 'pages': [_page(0, blocks, tables=tables)]}
    )
    assert (
        'table_contains_visual_or_empty_cells'
        in result['pages'][0]['regions'][0]['issues']
    )


def test_local_gap_detector_finds_uncovered_line_art_and_associates_region():
    image = Image.new('RGB', (1000, 1400), 'white')
    draw = ImageDraw.Draw(image)
    draw.rectangle((100, 100, 500, 180), fill='black')
    draw.rectangle((650, 300, 760, 390), outline='black', width=5)
    draw.line((660, 345, 750, 345), fill='black', width=5)
    buffer = BytesIO()
    image.save(buffer, format='PNG')
    page = _page(0, [_block('title', 100, 100, 500, 180, '94- سؤال')])
    candidates = detect_uncovered_graphics(
        image_bytes=buffer.getvalue(),
        page=page,
    )
    assert candidates
    analysis = analyze_ocr_document(
        {'model': 'mistral-ocr-4-0', 'pages': [page]}
    )
    associate_uncovered_graphics(analysis['pages'][0], candidates)
    assert (
        'uncovered_graphics_in_region'
        in analysis['pages'][0]['regions'][0]['issues']
    )
