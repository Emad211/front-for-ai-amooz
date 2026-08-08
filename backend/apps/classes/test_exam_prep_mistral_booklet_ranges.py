from apps.classes.services.exam_prep_mistral_booklet_ranges import (
    extract_booklet_ranges,
    parse_booklet_table,
)


def test_parse_booklet_table_uses_semantic_headers_not_free_text_ranges():
    html = (
        '<table><thead><tr><th>ردیف</th><th>مواد امتحانی</th>'
        '<th>تعداد سؤال</th><th>از شماره</th><th>تا شماره</th>'
        '<th>زمان پاسخگویی</th></tr></thead>'
        '<tr><td>۱</td><td>فیزیک</td><td>۳۰</td><td>۴۶</td>'
        '<td>۷۵</td><td>۳۰ دقیقه</td></tr>'
        '<tr><td>۲</td><td>شیمی</td><td>۳۵</td><td>۷۶</td>'
        '<td>۱۱۰</td><td>۳۵ دقیقه</td></tr></table>'
    )

    assert parse_booklet_table(html) == [
        {
            'subject': 'فیزیک',
            'questionCount': 30,
            'start': 46,
            'end': 75,
            'countMatchesRange': True,
        },
        {
            'subject': 'شیمی',
            'questionCount': 35,
            'start': 76,
            'end': 110,
            'countMatchesRange': True,
        },
    ]


def test_non_booklet_table_is_ignored():
    html = '<table><tr><th>نام درس</th><th>نام دبیر</th></tr><tr><td>زیست</td><td>الف</td></tr></table>'
    assert parse_booklet_table(html) == []


def test_extract_booklet_ranges_builds_contiguous_155_question_contract():
    def table(subject, count, start, end):
        return {
            'type': 'table',
            'content': (
                '<table><tr><th>مواد امتحانی</th><th>تعداد سؤال</th>'
                '<th>از شماره</th><th>تا شماره</th></tr>'
                f'<tr><td>{subject}</td><td>{count}</td><td>{start}</td><td>{end}</td></tr></table>'
            ),
        }

    root = {
        'pages': [
            {'index': 0, 'blocks': [table('زیست شناسی', 45, 1, 45)]},
            {
                'index': 1,
                'blocks': [
                    {
                        'type': 'table',
                        'content': (
                            '<table><tr><th>مواد امتحانی</th><th>تعداد سؤال</th>'
                            '<th>از شماره</th><th>تا شماره</th></tr>'
                            '<tr><td>فیزیک</td><td>۳۰</td><td>۴۶</td><td>۷۵</td></tr>'
                            '<tr><td>شیمی</td><td>۳۵</td><td>۷۶</td><td>۱۱۰</td></tr>'
                            '</table>'
                        ),
                    }
                ],
            },
            {
                'index': 2,
                'blocks': [
                    {
                        'type': 'table',
                        'content': (
                            '<table><tr><th>مواد امتحانی</th><th>تعداد سؤال</th>'
                            '<th>از شماره</th><th>تا شماره</th></tr>'
                            '<tr><td>ریاضی</td><td>۳۰</td><td>۱۱۱</td><td>۱۴۰</td></tr>'
                            '<tr><td>زمین شناسی</td><td>۱۵</td><td>۱۴۱</td><td>۱۵۵</td></tr>'
                            '</table>'
                        ),
                    }
                ],
            },
        ]
    }

    report = extract_booklet_ranges(root, original_page_numbers=[1, 9, 24])

    assert report['rangeCount'] == 5
    assert report['declaredQuestionCount'] == 155
    assert report['overallStart'] == 1
    assert report['overallEnd'] == 155
    assert report['gaps'] == []
    assert report['overlaps'] == []
    assert report['allCountsMatchRanges'] is True
