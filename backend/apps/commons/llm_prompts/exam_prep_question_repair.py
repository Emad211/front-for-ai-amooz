"""Prompt for targeted post-assembly question/source verification."""

EXAM_PREP_QUESTION_REPAIR_PROMPTS = {
    "exam_prep_question_repair": {
        "default": """
You verify and repair exactly ONE already-assembled exam question using only its supplied source page images and trustworthy native-text snippets.

Return one JSON object:
{
  "question_number": 18,
  "source_supported": true,
  "question_text_markdown": "complete readable Persian question stem",
  "options": [
    {"label": "1", "text_markdown": "complete option"}
  ],
  "correct_option_label": "3",
  "teacher_solution_markdown": "complete worked solution if visibly present",
  "final_answer_markdown": "short final answer if visibly present",
  "confidence": 0.0,
  "issues": []
}

Rules:
- Work only on REQUESTED_QUESTION_NUMBER. Never return another question.
- Use the current assembled question as a hint, not as truth.
- Locate the printed question number and its matching printed answer/solution in the supplied source pages.
- Source page order may be question page then answer page, or the reverse.
- In two-column answer pages, keep reading order and number boundaries separate. Do not attach continuation text from a neighboring numbered solution.
- A top fragment without a number may belong to the immediately preceding numbered solution only when the supplied continuation hint and page layout support it.
- Preserve readable Persian. Never copy visual-order Persian, Arabic Presentation Forms, or reversed text such as `؟تسا`.
- Prefer the image over a broken native-text layer. Native text is only supporting transcription evidence.
- Return complete option text. Never use bare labels as option text unless the source truly presents numeric count choices.
- If a worked solution is visibly present, include it completely. A correct-option label alone is not a worked solution.
- If the question depends on a figure/graph/diagram that is not faithfully represented, add `visual_evidence_required`.
- If the source pages do not support a safe repair, set source_supported=false, keep unsupported fields empty, and explain only with machine-readable issue codes.
- Do not invent medical/scientific content or solve the question from general knowledge.
- Return JSON only.
""".strip(),
    },
}
