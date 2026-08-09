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


def test_compact_cultural_table_normalizes_rtl_range_endpoints():
    html = (
        '<table><thead><tr><th>نام درس</th><th>تعداد سؤال</th>'
        '<th>شماره سؤال</th><th>وقت پیشنهادی (دقیقه)</th></tr></thead>'
        '<tr><td>تعلیم و تربیت اسلامی</td><td>۲۰</td><td>۲۷۰ - ۲۵۱</td><td>۲۰</td></tr>'
        '<tr><td>هوش و استعداد معلّمی</td><td>۲۰</td><td>۲۹۰ - ۲۷۱</td><td>۴۰</td></tr>'
        '<tr><td>جمع دروس</td><td>۴۰</td><td>—</td><td>۶۰</td></tr></table>'
    )

    assert parse_booklet_table(html) == [
        {
            'subject': 'تعلیم و تربیت اسلامی',
            'questionCount': 20,
            'start': 251,
            'end': 270,
            'countMatchesRange': True,
        },
        {
            'subject': 'هوش و استعداد معلّمی',
            'questionCount': 20,
            'start': 271,
            'end': 290,
            'countMatchesRange': True,
        },
    ]


def test_compact_table_ignores_numeric_aggregate_row():
    html = (
        '<table><thead><tr><th>شماره سؤال</th><th>تعداد سؤال</th><th>نام درس</th></tr></thead>'
        '<tr><td>۴۱-۷۵</td><td>۳۵</td><td>فیزیک</td></tr>'
        '<tr><td>۷۶-۱۰۵</td><td>۳۰</td><td>شیمی</td></tr>'
        '<tr><td>۴۱-۱۰۵</td><td>۶۵</td><td>جمع کل</td></tr></table>'
    )
    rows = parse_booklet_table(html)
    assert [(row['start'], row['end']) for row in rows] == [(41, 75), (76, 105)]


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
