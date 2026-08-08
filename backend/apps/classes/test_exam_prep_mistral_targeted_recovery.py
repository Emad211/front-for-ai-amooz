from apps.classes.services.exam_prep_mistral_targeted_recovery import (
    resolve_target_questions,
    scan_solution_headings,
)


def test_scan_solution_headings_finds_multiple_headings_inside_one_block():
    content = """۵۵ - گزینه «۴»\nمتن پاسخ\n۵۶ - گزینه «۴»\nمتن پاسخ\n۵۷ - گزینه «۳»"""

    headings = scan_solution_headings(content)

    assert [item["rawQuestionNumber"] for item in headings] == [55, 56, 57]
    assert [item["optionLabel"] for item in headings] == [4, 4, 3]


def test_scan_solution_headings_reads_headings_inside_html_table():
    content = (
        "<table><tr><td>۱۰ - گزینه ۲</td><td>teacher</td></tr>"
        "<tr><td>۱۱ - گزینه ۳</td><td>teacher</td></tr></table>"
    )

    headings = scan_solution_headings(content)

    assert [item["rawQuestionNumber"] for item in headings] == [10, 11]
    assert [item["optionLabel"] for item in headings] == [2, 3]


def test_target_resolution_ignores_non_target_bad_headings():
    headings = [
        {
            "rawQuestionNumber": 10,
            "rawOptionLabel": 2,
            "optionLabel": 2,
            "optionLabelValid": True,
            "physicalPageNumber": 34,
        },
        {
            "rawQuestionNumber": 12,
            "rawOptionLabel": 4,
            "optionLabel": 4,
            "optionLabelValid": True,
            "physicalPageNumber": 34,
        },
        {
            "rawQuestionNumber": 13,
            "rawOptionLabel": 5,
            "optionLabel": 5,
            "optionLabelValid": False,
            "physicalPageNumber": 34,
        },
    ]

    report = resolve_target_questions(headings, [10])

    assert report["complete"] is True
    assert report["recovered"] == [
        {
            "questionNumber": 10,
            "optionLabel": 2,
            "evidenceCount": 1,
            "physicalPages": [34],
        }
    ]
    assert report["unresolvedQuestionNumbers"] == []
    assert report["conflicts"] == []


def test_target_resolution_fails_closed_on_conflicting_valid_options():
    headings = [
        {
            "rawQuestionNumber": 57,
            "optionLabel": 2,
            "optionLabelValid": True,
            "physicalPageNumber": 40,
        },
        {
            "rawQuestionNumber": 57,
            "optionLabel": 3,
            "optionLabelValid": True,
            "physicalPageNumber": 40,
        },
    ]

    report = resolve_target_questions(headings, [57])

    assert report["complete"] is False
    assert report["recovered"] == []
    assert report["conflicts"] == [
        {"questionNumber": 57, "validOptionLabels": [2, 3]}
    ]
