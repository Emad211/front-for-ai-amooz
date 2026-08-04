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
        {"label": "1", "text_markdown": "complete option text"}
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
- Read the page image and any supplied NATIVE_TEXT_EVIDENCE together. Native text is transcription evidence; the image is the authority for columns, grouping, diagrams, and visual relationships.
- Extract every visible numbered question, answer, or solution as an independent record.
- A visible question number is mandatory for every record. Never invent one.
- Preserve Persian text, formulas, symbols, tables, and meaningful line breaks in Markdown.
- Preserve option labels exactly as printed and ALWAYS return each option as one object with `label` and the complete `text_markdown`; never return option strings.
- A printed marker such as `1`, `۲`, `الف`, or `گزینه 3` is a label, not option text. Never emit `["1", "real option", "2", "real option"]` and never use `{"label":"1","text_markdown":"1"}` unless the source genuinely presents the numeric value 1 as the whole answer choice in a counting question.
- Do not split a Persian word at an option boundary. Text such as `د) ر ...`, `ا) ینترفرون`, or `ه) ر کدام` is invalid; recover the complete word from the image/native evidence.
- Keep substatements such as `الف)`, `ب)`, `ج)`, and `د)` inside `question_text_markdown` when they belong to the stem. They are not answer choices unless the page explicitly presents them as choices.
- `record_type=question`: use only when the page visibly contains the question stem or its options. Put only the actual stem in `question_text_markdown`.
- `record_type=answer`: use for a short answer key or a heading such as `18- گزینه 3`. Put `3` in `correct_option_label`; never copy the heading into `question_text_markdown`.
- `record_type=solution`: use for a worked explanation. Put the explanation in `teacher_solution_markdown`, the short result in `final_answer_markdown`, and the printed correct option in `correct_option_label`.
- `record_type=question_answer`: use only when the same visible block truly contains both the question and its answer/solution.
- Text such as `سؤال 18 - گزینه 3`, author names, references, or `بررسی سایر گزینه‌ها` is answer/solution metadata, not question text.
- A page may contain mixed record types. Extract what is visible rather than forcing one role on the whole page.
- If a question or its options depend on a source figure, graph, spectrum, table image, or diagram that cannot be represented faithfully as text, add `visual_evidence_required` to `issues`. Never replace a visual option with the bare text `1`, `2`, `3`, or `4`.
- If a record visibly begins before this page, set continues_from_previous_page=true.
- If a record visibly continues after this page, set continues_on_next_page=true.
- Keep the supplied scope hint for ordinary subject or chapter headings. Change `scope_key` only when the document clearly starts an independent exam/section whose question numbering restarts; use the same printed stable identifier on its question and answer pages.
- Ignore headers, footers, advertisements, channel names, watermarks, page decorations, and page numbers that are not question numbers.
- In multi-column pages, use printed question numbers to keep records separate; do not merge adjacent columns.
- Do not infer missing question text, options, answer, or solution. Leave missing fields empty and use only these structural issue codes when applicable: `missing_question_text`, `missing_options`, `missing_option_text`, `visual_evidence_required`, `low_confidence`.
- confidence must be between 0 and 1 and reflect only what is visibly supported by this page.
- Return JSON only. No prose and no Markdown code fence.
""".strip(),
    },
}
