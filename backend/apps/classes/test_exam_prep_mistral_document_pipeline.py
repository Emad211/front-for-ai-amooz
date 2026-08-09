from apps.classes.services.exam_prep_mistral_document_pipeline import (
    _question_record,
    _target_crop_specs,
    parse_question_region_text,
)
from apps.classes.services.exam_prep_mistral_solution_headings import (
    AlignedSolutionHeading,
)


def test_parse_standard_numeric_options():
    stem, options, style = parse_question_region_text(
        '۱- متن سؤال\nالف) گزاره\n۱) الف و د ۲) الف و ب ۳) ج ۴) د'
    )
    assert stem.startswith('متن سؤال')
    assert [item['label'] for item in options] == ['1', '2', '3', '4']
    assert [item['text_markdown'] for item in options] == ['الف و د', 'الف و ب', 'ج', 'د']
    assert style == 'prefix'


def test_parse_rtl_provider_reversed_options():
    _stem, options, style = parse_question_region_text(
        '۲- متن سؤال\n۴) چهار ۳) سه ۲) دو ۱) یک'
    )
    assert [(item['label'], item['text_markdown']) for item in options] == [
        ('1', 'یک'),
        ('2', 'دو'),
        ('3', 'سه'),
        ('4', 'چهار'),
    ]
    assert style == 'prefix'


def test_parse_parenthesized_prefix_options():
    _stem, options, style = parse_question_region_text(
        '۲۰- کدام درست است؟\n(۱) اول\n(۲) دوم\n(۳) سوم\n(۴) چهارم'
    )
    assert [item['text_markdown'] for item in options] == ['اول', 'دوم', 'سوم', 'چهارم']
    assert style == 'parenthesized_prefix'


def test_parse_parenthesized_suffix_count_options():
    _stem, options, style = parse_question_region_text(
        '۹- چند مورد درست است؟\nالف) ...\nب) ...\n۲(۱) ۳(۲) ۴(۳) ۱(۴)'
    )
    assert [(item['label'], item['text_markdown']) for item in options] == [
        ('1', '۲'),
        ('2', '۳'),
        ('3', '۴'),
        ('4', '۱'),
    ]
    assert style == 'suffix'


def test_visual_only_question_gets_four_source_placeholders():
    record = _question_record(
        {
            'questionNumber': 65,
            'text': '۶۵- کدام مدار درست است؟',
            'bbox': [0.0, 0.2, 1.0, 0.8],
            'visuals': [{'type': 'image'}],
            'issues': ['visual_options_grouped_in_single_block'],
        }
    )
    assert record is not None
    assert len(record['options']) == 4
    assert record['options'][0]['text_markdown'].startswith('گزینهٔ تصویری')
    assert 'visual_options_source_crop_authoritative' in record['issues']


def _heading(question, page, column, option=1, valid=True):
    return AlignedSolutionHeading(
        physical_page_number=page,
        provider_block_index=0,
        column=column,
        raw_question_number=question,
        question_number=question,
        raw_option_label=option,
        option_label=option if valid else None,
        option_label_normalized=False,
        option_label_valid=valid,
        question_number_recovered=False,
        recovery_reason=None,
    )


def test_missing_solution_targets_choose_next_heading_column_and_dedupe():
    accepted = [
        _heading(3, 33, 'right'),
        _heading(7, 33, 'left'),
        _heading(9, 34, 'right'),
        _heading(11, 34, 'left'),
        _heading(16, 35, 'right'),
    ]
    specs = _target_crop_specs(accepted, [4, 5, 6, 10, 15])
    assert specs == [(33, 'left'), (34, 'left'), (35, 'right')]
