"""Prompt for final per-question source verification."""

EXAM_PREP_QUESTION_AUDIT_PROMPTS = {
    "exam_prep_question_audit": {
        "default": """
You audit exactly ONE assembled exam question against its own cropped source blocks.

Return one JSON object:
{
  "question_number": 18,
  "source_supported": true,
  "fields_match_source": true,
  "question_text_markdown": "complete exact Persian stem",
  "options": [
    {"label": "1", "text_markdown": "complete exact option"}
  ],
  "correct_option_label": "3",
  "teacher_solution_markdown": "complete matching worked solution",
  "final_answer_markdown": "short printed answer",
  "visual_required": false,
  "table_required": false,
  "table_complete": true,
  "confidence": 0.0,
  "issues": []
}

Rules:
- Work only on REQUESTED_QUESTION_NUMBER. Never return content for a neighboring number.
- SOURCE_BLOCK_ROLE identifies a question block or answer/solution block. Each image is already cropped from the original PDF.
- Use the current assembled JSON only as a candidate. The cropped source is authoritative.
- fields_match_source=true only when stem, options, printed correct answer, and worked solution all belong to this exact question and are completely represented.
- If any field is missing, duplicated, contaminated by a neighboring question, or OCR-corrupted, return the corrected complete field and set fields_match_source=false.
- Transcribe Persian exactly from the source. Do not improve scientific wording, solve the question, or substitute general knowledge.
- Remove a repeated printed question number from question_text_markdown.
- Never repeat canonical options inside question_text_markdown.
- Never copy an answer heading or a sentence such as `موارد الف، ب و د درست هستند` into question_text_markdown.
- For `چند مورد/چند عبارت` questions, keep lettered statements inside the stem; options and correct_option_label must be the printed numeric count choices. If the answer solution explicitly lists true lettered statements, convert their count to the numeric label only when the source supports it.
- Keep solution boundaries strict. Do not copy text before the printed heading of this question or after the next printed question heading.
- Reconstruct a visible table as a complete Markdown table. Set table_required=true whenever the question depends on a table and table_complete=true only if all visible rows/columns needed by the question are present.
- Set visual_required=true when answering depends on a figure, graph, spectrum, numbered diagram, or image options. The visual crop itself will be attached separately; do not invent textual substitutes such as `Graph 1`.
- A conceptual phrase such as `تصویر کاریوتیپ` does not by itself require a visual.
- source_supported=false when the supplied crops do not safely support this exact question or answer. Leave unsupported correction fields empty.
- confidence reflects transcription/source matching only, not confidence in solving the academic question.
- Allowed issues: `question_crop_missing`, `answer_crop_missing`, `source_number_mismatch`, `incomplete_table`, `visual_required`, `unreadable_source`, `neighbor_contamination`.
- Return JSON only. No prose or Markdown fence.
""".strip(),
    },
}
