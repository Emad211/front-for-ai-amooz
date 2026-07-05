"""Contract regression tests for the central PROMPTS repository.

The prompt re-architecture (2026-06-07) rewrote prompt *wording* for production
(safety preamble, level-adaptive language, injection guards, MCQ rubrics) while
the callers still depend on EXACT contracts:

* the set of live keys/sub-keys (callers look prompts up by literal key),
* the load-bearing placeholder tokens each template must contain (rendered via
  ``str.replace`` — a dropped token silently no-ops), and
* the output-JSON key strings downstream parsers / Pydantic models / frontend
  widgets read.

These checks are pure string assertions over the imported dict — zero LLM calls,
zero tokens. They are the guard against contract drift in any future edit.

Sources of truth for the maps below:
* placeholders  -> the ``str.replace`` / ``_render_prompt`` / ``_safe_template_replace``
  call sites in apps/classes/services/{quizzes,recap,structure,prerequisites,
  exam_prep_structure}.py and apps/chatbot/services/{student_course_chat,
  student_exam_prep_chat,memory_service,llm_client}.py
* output keys   -> the JSON the same call sites parse, plus
  apps/classes/services/schemas.py
"""
import pytest

from apps.commons.llm_prompts.prompts import (
    PROMPTS,
    SAFETY_PREAMBLE,
    AUDIENCE_ADAPTIVE,
    MCQ_QUALITY,
    MATH_FORMAT_INSTRUCTIONS,
)

pytestmark = pytest.mark.unit


# --- The authoritative live-key map (top-level key -> expected sub-keys) ------
# A value of None means the top-level value is a plain string prompt.
LIVE_KEYS = {
    "pdf_extraction": ["default"],
    "prerequisites_prompt": ["default"],
    "prerequisite_teaching": ["default"],
    "structure_content": ["default"],
    "recap_and_notes": ["default"],
    "exam_prep_structure": ["default"],
    "exercise_structure": ["default"],
    "exercise_grading": ["default"],
    "chat_intent": None,
    "chat_system_prompt": None,
    "image_plan": ["default"],
    "text_grading": ["default"],
    "exam_prep_hint": ["default"],
    "json_repair": ["default"],
    "chat_image_description": ["default"],
    "final_exam_pool": ["default", "adaptive"],
    "section_quiz": ["default", "adaptive"],
    "transcribe_media": ["default", "chunked"],
    "memory_summary": ["default"],
    "exam_prep_chat": ["default"],
    "exam_prep_handwriting_vision": ["default"],
    "notes_ai": ["detailed_notes"],
    "fetch_quizzes": ["multiple_choice"],
    "practice_tests": ["mixed_questions"],
    "flash_cards": ["standard_qa"],
    "match_games": ["term_definition"],
    "meril": ["problem_centered"],
}

# --- Keys that were audited as DEAD and removed -------------------------------
DEAD_TOP_LEVEL = [
    "chat_simple_example",
    "chat_activation_start",
    "chat_activation_continue",
    "chat_unit_intro",
    "question_bank_batch",
    "rewrite",
    "activation",
    "assessment",
    "course_final_exam",
]
# (top-level key, dead sub-key that must be gone while the parent stays)
DEAD_SUB_KEYS = [
    ("notes_ai", "concise_summary"),
    ("fetch_quizzes", "short_quiz"),
    ("meril", "integration"),
]


def _text(key, sub=None) -> str:
    node = PROMPTS[key]
    if sub is not None:
        node = node[sub]
    # pdf_extraction.default is built with parenthesised concatenation -> str.
    return str(node)


# Required placeholder tokens per (key, sub). Rendered by the caller; must stay.
PLACEHOLDERS = {
    ("chat_intent", None): ["{user_message}"],
    ("chat_system_prompt", None): [
        "{student_name}", "{unit_content}", "{history_str}", "{user_message}",
    ],
    ("image_plan", "default"): ["{unit_content}", "{user_message}"],
    ("text_grading", "default"): ["{question}", "{reference_answer}", "{student_answer}"],
    ("exercise_grading", "default"): ["{grading_items_json}"],
    ("exam_prep_hint", "default"): [
        "{question}", "{student_answer}", "{reference_answer}", "{attempt_number}",
    ],
    ("json_repair", "default"): ["{feature}", "{schema_hint}", "{raw_text}"],
    ("chat_image_description", "default"): ["{unit_content}", "{user_message}"],
    ("final_exam_pool", "default"): ["{pool_size}", "{combined_content}"],
    ("final_exam_pool", "adaptive"): [
        "{pool_size}", "{review_count}", "{weak_points_json}", "{combined_content}",
    ],
    ("section_quiz", "default"): ["{count}", "{section_content}", "{{blank}}"],
    ("section_quiz", "adaptive"): [
        "{count}", "{review_count}", "{weak_points_json}", "{section_content}", "{{blank}}",
    ],
    ("memory_summary", "default"): ["{old_summary}", "{new_turns}"],
    # Chunked transcription continuation block (services/transcription.py).
    ("transcribe_media", "chunked"): [
        "{part_number}", "{total_parts}", "{previous_transcript_tail}",
    ],
    ("exam_prep_chat", "default"): [
        "{question_context}", "{student_selected}", "{is_checked}", "{is_correct}",
        "{image_description}", "{history}", "{user_message}",
    ],
    ("exam_prep_handwriting_vision", "default"): ["{question_context}", "{user_message}"],
    ("notes_ai", "detailed_notes"): ["STRUCTURED_BLOCKS_JSON"],
    ("fetch_quizzes", "multiple_choice"): ["STRUCTURED_BLOCKS_JSON", "{num_questions}"],
    ("practice_tests", "mixed_questions"): ["STRUCTURED_BLOCKS_JSON", "{num_questions}"],
    ("flash_cards", "standard_qa"): ["STRUCTURED_BLOCKS_JSON", "{num_flashcards}"],
    ("match_games", "term_definition"): ["STRUCTURED_BLOCKS_JSON", "{num_pairs}"],
    ("meril", "problem_centered"): ["STRUCTURED_BLOCKS_JSON"],
}

# Required output-JSON key strings per (key, sub). Downstream parsers read these.
OUTPUT_KEYS = {
    ("prerequisites_prompt", "default"): ["prerequisites"],
    ("structure_content", "default"): [
        "root_object", "outline", "what_you_will_learn", "merrill_type",
        "source_markdown", "content_markdown", "image_ideas",
    ],
    ("recap_and_notes", "default"): [
        "recap", "overview_markdown", "key_notes_markdown", "by_unit",
        "section_title", "unit_title", "unit_recap_markdown",
        "unit_key_points_markdown", "common_mistakes_markdown",
        "quick_self_check_markdown", "formula_sheet_markdown",
    ],
    ("exam_prep_structure", "default"): [
        "exam_prep", "question_text_markdown", "options", "correct_option_label",
        "teacher_solution_markdown", "final_answer_markdown",
    ],
    ("exercise_structure", "default"): [
        "exercise_title", "sections", "questions", "question_id",
        "question_text_markdown", "question_type", "options", "points",
        "reference_answer_markdown",
    ],
    ("chat_intent", None): ["intent"],
    ("chat_system_prompt", None): ["content", "suggestions"],
    ("image_plan", "default"): ["images", "caption"],
    ("text_grading", "default"): ["score_0_100", "label", "feedback", "missing_points"],
    ("exercise_grading", "default"): [
        "per_question", "question_id", "score_points", "max_points", "label",
        "feedback", "missing_points",
    ],
    ("exam_prep_hint", "default"): ["hint", "encouragement"],
    ("final_exam_pool", "default"): ["exam_title", "questions", "correct_answer", "points"],
    ("final_exam_pool", "adaptive"): ["exam_title", "questions", "correct_answer", "points"],
    ("section_quiz", "default"): ["questions", "correct_answer", "difficulty"],
    ("section_quiz", "adaptive"): ["questions", "correct_answer", "difficulty"],
    ("exam_prep_chat", "default"): ["content", "suggestions"],
    ("exam_prep_handwriting_vision", "default"): [
        "description_markdown", "extracted_text_markdown", "clean_steps_markdown",
        "unclear_parts",
    ],
    ("notes_ai", "detailed_notes"): ["items", "related_unit_id", "notes_markdown"],
    ("fetch_quizzes", "multiple_choice"): [
        "questions", "related_unit_id", "correct_answer", "explanation",
    ],
    ("practice_tests", "mixed_questions"): ["test_items", "related_unit_id"],
    ("flash_cards", "standard_qa"): ["flashcards", "front", "back", "card_type"],
    ("match_games", "term_definition"): ["pairs", "term", "definition"],
    ("meril", "problem_centered"): ["scenarios", "challenge_question", "solution_hint"],
}


def test_all_live_keys_present_with_expected_subkeys():
    for key, subs in LIVE_KEYS.items():
        assert key in PROMPTS, f"live prompt key missing: {key}"
        if subs is None:
            assert isinstance(PROMPTS[key], str), f"{key} should be a plain string prompt"
        else:
            assert isinstance(PROMPTS[key], dict), f"{key} should be a dict of strategies"
            for sub in subs:
                assert sub in PROMPTS[key], f"missing sub-key {key}.{sub}"
                assert str(PROMPTS[key][sub]).strip(), f"empty prompt at {key}.{sub}"


def test_no_unexpected_top_level_keys():
    """Catch accidental re-introduction of a dead/typo'd key."""
    extra = set(PROMPTS.keys()) - set(LIVE_KEYS.keys())
    assert not extra, f"unexpected top-level PROMPTS keys: {sorted(extra)}"


def test_dead_top_level_keys_removed():
    for key in DEAD_TOP_LEVEL:
        assert key not in PROMPTS, f"dead prompt key should be removed: {key}"


def test_dead_sub_keys_removed_parent_kept():
    for parent, sub in DEAD_SUB_KEYS:
        assert parent in PROMPTS, f"parent unexpectedly removed: {parent}"
        assert sub not in PROMPTS[parent], f"dead sub-key should be removed: {parent}.{sub}"


@pytest.mark.parametrize("loc,tokens", list(PLACEHOLDERS.items()))
def test_required_placeholders_present(loc, tokens):
    key, sub = loc
    text = _text(key, sub)
    for tok in tokens:
        assert tok in text, f"placeholder {tok!r} missing from {key}.{sub}"


@pytest.mark.parametrize("loc,keys", list(OUTPUT_KEYS.items()))
def test_required_output_keys_present(loc, keys):
    key, sub = loc
    text = _text(key, sub)
    for k in keys:
        assert k in text, f"output JSON key {k!r} missing from {key}.{sub}"


def test_no_hardcoded_k12_in_live_prompts():
    """The platform serves any level; the old hardcoded 'K-12' framing is gone."""
    for key, subs in LIVE_KEYS.items():
        if subs is None:
            assert "K-12" not in PROMPTS[key], f"'K-12' should be gone from {key}"
        else:
            for sub in subs:
                assert "K-12" not in str(PROMPTS[key][sub]), f"'K-12' should be gone from {key}.{sub}"


def test_shared_safety_block_injected_into_untrusted_content_prompts():
    """Prompts that consume untrusted user content carry the safety preamble."""
    must_have_safety = [
        ("pdf_extraction", "default"),
        ("structure_content", "default"),
        ("recap_and_notes", "default"),
        ("prerequisites_prompt", "default"),
        ("exam_prep_structure", "default"),
        ("exercise_structure", "default"),
        ("chat_system_prompt", None),
        ("text_grading", "default"),
        ("exercise_grading", "default"),
        ("exam_prep_chat", "default"),
    ]
    anchor = SAFETY_PREAMBLE.splitlines()[0]  # "### Safety & integrity (always apply)"
    for key, sub in must_have_safety:
        assert anchor in _text(key, sub), f"safety preamble missing from {key}.{sub}"


def test_mcq_quality_block_in_quiz_generators():
    anchor = MCQ_QUALITY.splitlines()[0]
    for key, sub in [
        ("section_quiz", "default"),
        ("section_quiz", "adaptive"),
        ("final_exam_pool", "default"),
        ("final_exam_pool", "adaptive"),
        ("fetch_quizzes", "multiple_choice"),
        ("practice_tests", "mixed_questions"),
    ]:
        assert anchor in _text(key, sub), f"MCQ quality block missing from {key}.{sub}"


def test_math_block_constant_nonempty():
    assert "\\frac" in MATH_FORMAT_INSTRUCTIONS
    assert AUDIENCE_ADAPTIVE.strip()
