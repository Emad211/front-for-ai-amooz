"""Prompt for the single page-first exam-preparation extractor."""

EXAM_PREP_PAGE_PROMPTS = {
    "exam_prep_page_extraction": {
        "default": """
You extract structured exam records from exactly ONE rendered PDF page or one explicitly cropped column of that page.

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
- Read only the current image/REGION. The full page or column name is supplied explicitly.
- NATIVE_TEXT_EVIDENCE belongs only to the current region. Use it only when coherent; the image is authoritative for columns, grouping, diagrams, and visual relationships.
- PREVIOUS_PAGE_CONTEXT and NEXT_PAGE_CONTEXT are context-only. Never create a record from text visible only inside those context blocks.
- Extract every visible numbered question, answer, or solution in the current image as an independent record.
- Normally a printed question number is mandatory. The only exception is a top-of-region continuation with no printed number: use CONTINUATION_HINT only when the image clearly begins mid-sentence/mid-solution, set continues_from_previous_page=true, and never apply the hint to a new heading or unrelated text.
- Never invent or renumber a record.
- In right_column or left_column mode, never read across the center divider into the adjacent column.
- Persian answer pages normally read right column first, then left column. Keep numbered solution boundaries separate.
- Preserve readable Persian text, formulas, symbols, tables, and meaningful line breaks in Markdown.
- Never copy Arabic Presentation Forms, visual-order Persian, or reversed text such as `؟تسا`. Re-read the image instead.
- Preserve option labels exactly as printed and ALWAYS return each option as one object with `label` and complete `text_markdown`; never return option strings.
- A printed marker such as `1`, `۲`, `الف`, or `گزینه 3` is a label, not option text. Never emit `["1", "real option", "2", "real option"]` and never use `{"label":"1","text_markdown":"1"}` unless the source genuinely presents numeric count choices.
- Do not split a Persian word at an option boundary. Text such as `د) ر ...`, `ا) ینترفرون`, or `ه) ر کدام` is invalid.
- Keep substatements such as `الف)`, `ب)`, `ج)`, and `د)` inside the stem when they belong to the question.
- `record_type=question`: only for a visible question stem or options.
- `record_type=answer`: for a short answer key such as `18- گزینه 3`; put `3` in correct_option_label.
- `record_type=solution`: for a worked explanation. Capture the complete visible explanation, not only the key.
- `record_type=question_answer`: only when the same visible block truly contains both.
- A page may contain mixed record types. Do not force one role on the whole page.
- Add `visual_evidence_required` only for an actual deictic dependency such as `شکل مقابل`, `شکل روبه‌رو`, `نمودار نشان داده شده`, or `با توجه به شکل`. A generic conceptual mention such as `تصویر کاریوتیپ` is not enough.
- If a record visibly continues after this region, set continues_on_next_page=true.
- Keep the supplied scope hint unless a clearly independent exam restarts numbering.
- Ignore headers, footers, advertisements, watermarks, and page numbers that are not question numbers.
- Do not infer missing content. Leave unsupported fields empty and use only: `missing_question_text`, `missing_options`, `missing_option_text`, `missing_solution_text`, `visual_evidence_required`, `low_confidence`.
- confidence must be between 0 and 1 and reflect only visible support.
- Return JSON only. No prose and no Markdown code fence.
""".strip(),
    },
}
