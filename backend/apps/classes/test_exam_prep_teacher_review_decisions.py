from apps.classes.services.exam_prep_page_review import audit_page_first_projection


def _question(*, issues=None, reviewed=None, options=None, visuals=None):
    return {
        'question_id': 'default-q-44',
        'scope_key': 'default',
        'section_key': 'default',
        'source_question_number': '44',
        'question_text_markdown': 'کدام گزینه درست است؟',
        'options': options if options is not None else [
            {'label': '1', 'text_markdown': 'گزینه یک'},
            {'label': '2', 'text_markdown': 'گزینه دو'},
            {'label': '3', 'text_markdown': 'گزینه سه'},
            {'label': '4', 'text_markdown': 'گزینه چهار'},
        ],
        'correct_option_label': '2',
        'correct_option_text_markdown': 'گزینه دو',
        'teacher_solution_markdown': 'راه‌حل تشریحی کامل برای سؤال چهل و چهار',
        'final_answer_markdown': 'گزینه 2',
        'confidence': 0.9,
        'issues': list(issues or []),
        'teacher_reviewed_issue_codes': list(reviewed or []),
        'source_pages': [7, 14],
        'visuals': list(visuals or []),
    }


def _audit(question):
    return audit_page_first_projection({
        'exam_prep': {'title': 'آزمون', 'questions': [question]},
    })


def test_teacher_can_acknowledge_source_verification_failure():
    audit = _audit(_question(
        issues=['source_verification_failed'],
        reviewed=['source_verification_failed'],
    ))

    assert audit['status'] == 'passed'
    assert audit['criticalIssueCount'] == 0


def test_teacher_acknowledgement_cannot_hide_structural_option_error():
    audit = _audit(_question(
        issues=['missing_option_text'],
        reviewed=['missing_option_text'],
        options=[
            {'label': '1', 'text_markdown': ''},
            {'label': '2', 'text_markdown': 'گزینه دو'},
        ],
    ))

    assert audit['status'] == 'needs_review'
    assert 'missing_option_text' in {item['code'] for item in audit['issues']}


def test_attached_question_visual_satisfies_visual_evidence_requirement():
    audit = _audit(_question(
        issues=['visual_evidence_required'],
        visuals=[
            {
                'id': 'inline-default-q-44',
                'role': 'question',
                'altText': 'شکل سؤال',
                'dataUrl': 'data:image/jpeg;base64,AA==',
            }
        ],
    ))

    assert audit['status'] == 'passed'
    assert 'visual_evidence_required' not in {
        item['code'] for item in audit['issues']
    }
