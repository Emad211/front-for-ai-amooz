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
- Preserve option labels exactly as printed and pair each label with its option text.
- For an answer key, fill correct_option_label and/or correct_option_text_markdown.
- For a worked solution, fill teacher_solution_markdown and final_answer_markdown when visible.
- A page may contain mixed record types. Extract what is visible rather than forcing one role on the whole page.
- If a record visibly begins before this page, set continues_from_previous_page=true.
- If a record visibly continues after this page, set continues_on_next_page=true.
- Use the supplied scope hint unless the page clearly prints a different local exam/section identifier.
- Ignore headers, footers, advertisements, channel names, watermarks, and page decorations.
- In multi-column pages, use printed question numbers to keep records separate; do not merge adjacent columns.
- Do not infer missing question text, options, answer, or solution. Leave missing fields empty and add a short machine-readable issue code.
- confidence must be between 0 and 1 and reflect only what is visibly supported by this page.
- Return JSON only. No prose and no Markdown code fence.
""".strip(),
    },
}
