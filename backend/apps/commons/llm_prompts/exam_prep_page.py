"""Prompt for the single page-first exam-preparation extractor."""

EXAM_PREP_PAGE_PROMPTS = {
    "exam_prep_page_extraction": {
        "default": """
You extract structured exam records from exactly ONE rendered PDF page.

Return one JSON object matching this shape:
{
  "page_number": 1,
  "records": [
    {
      "scope_key": "default",
      "question_number": 51,
      "record_type": "question|answer|solution|question_answer",
      "question_text_markdown": "",
      "options": [
        {"label": "1", "text_markdown": ""}
      ],
      "correct_option_label": null,
      "correct_option_text_markdown": "",
      "teacher_solution_markdown": "",
      "final_answer_markdown": "",
      "continues_from_previous_page": false,
      "continues_on_next_page": false,
      "confidence": 0.0,
      "issues": []
    }
  ]
}

Rules:
- Read the page itself. Do not globally classify the page and do not return a page type.
- Extract every visible numbered question, answer, or solution as an independent record.
- A visible question number is mandatory for every record. Never invent one.
- Preserve Persian text, formulas, symbols, tables, and meaningful line breaks in Markdown.
- Preserve option labels exactly as printed and ALWAYS return each option as an object with `label` and `text_markdown`; never return option strings.
- `record_type=question`: use only when the page visibly contains the question stem or its options. Put only the actual stem in `question_text_markdown`.
- `record_type=answer`: use for a short answer key or a heading such as `18- گزینه 3`. Put `3` in `correct_option_label`; never copy the heading into `question_text_markdown`.
- `record_type=solution`: use for a worked explanation. Put the explanation in `teacher_solution_markdown`, the short result in `final_answer_markdown`, and the printed correct option in `correct_option_label`.
- `record_type=question_answer`: use only when the same visible block truly contains both the question and its answer/solution.
- Text such as `سؤال 18 - گزینه 3`, author names, references, or `بررسی سایر گزینه‌ها` is answer/solution metadata, not question text.
- A page may contain mixed record types. Extract what is visible rather than forcing one role on the whole page.
- If a record visibly begins before this page, set continues_from_previous_page=true.
- If a record visibly continues after this page, set continues_on_next_page=true.
- Use the supplied scope hint unless a clearly printed local subject/section heading changes (for example Biology to Physics); then use a short stable scope key for that printed section.
- Ignore headers, footers, advertisements, channel names, watermarks, page decorations, and page numbers that are not question numbers.
- In multi-column pages, use printed question numbers to keep records separate; do not merge adjacent columns.
- Do not infer missing question text, options, answer, or solution. Leave missing fields empty and add a short machine-readable issue code.
- confidence must be between 0 and 1 and reflect only what is visibly supported by this page.
- Return JSON only. No prose and no Markdown code fence.
""".strip(),
    },
}
