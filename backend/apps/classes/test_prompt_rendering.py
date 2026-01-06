from apps.classes.services.quizzes import _render_prompt
from apps.commons.llm_prompts.prompts import PROMPTS


def test_render_prompt_does_not_break_json_braces_for_section_quiz():
    rendered = _render_prompt(PROMPTS['section_quiz']['default'], count=5, section_content='x')
    assert '"questions"' in rendered
    assert '{count}' not in rendered
    assert '{section_content}' not in rendered


def test_render_prompt_does_not_break_json_braces_for_final_exam_pool():
    rendered = _render_prompt(PROMPTS['final_exam_pool']['default'], pool_size=12, combined_content='x')
    assert '"exam_title"' in rendered
    assert '{pool_size}' not in rendered
    assert '{combined_content}' not in rendered
