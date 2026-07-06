# Exercise Hub LaTeX Rendering Audit

Date: 2026-07-07

Scope: Exercise Hub frontend surfaces introduced around E10-E12c, plus the dashboard calendar/home event surfaces that now receive exercise-deadline titles from E12.

## Result

All user-facing dynamic exercise math content is now routed through the right renderer:

- Short, one-line labels/titles use `MathText`:
  - student exercise hub: exercise title, class/course title, deadline agenda rows
  - student report-card rows
  - student solver title and section chips
  - finished-answers exercise/course/section titles
  - teacher exercise list title and section accordion title
  - dashboard calendar event badges/cards/modal and home upcoming-event card
- Markdown/body content uses `MarkdownWithMath`:
  - student solver question text
  - result page question text, feedback, teacher feedback, revealed reference answer
  - finished-answers question text and reference answer
  - assistant replies
  - teacher gradebook student text answers and automatic feedback

## Verified

Static checks:

- `rg` audit found no remaining raw rendering of Exercise Hub dynamic `title`/`courseTitle`/`exerciseTitle`/`subject`/`description` fields in the new exercise/calendar surfaces, except non-rendering browser tooltip text (`title={event.title}`).
- `frontend && npx tsc --noEmit` stays at the existing 13-error baseline; no errors in touched files.

Browser checks on the real local stack:

- Seeded a class, exercise, section, questions, reference answers, submission answers, and grading feedback with LaTeX such as `\(x^2+2x+1\)`, `\(a^2+b^2=c^2\)`, `\(P(x)\)`, `\(2+2=4\)`, and `\(f(3)=9\)`.
- Verified DOM `.katex` count and absence of raw `\(` / `$x^2` on:
  - `/exercises` student hub/report-card/catalog
  - `/exercises/1?session=1` solver
  - `/exercises/1/result?session=1` result page
  - `/exercises/answers` finished answers browse
  - `/calendar` calendar grid/sidebar
  - `/teacher/my-classes/1/exercises` teacher list/editor/gradebook dialog

## Notes

- `MathText` is intentionally used for compact labels because `MarkdownWithMath` wraps content in block paragraph markup and is not safe inside headings, flex rows, badges, or accordion triggers.
- Textareas remain raw by design: authoring fields should preserve the editable source LaTeX while the rendered surfaces display KaTeX.
