import type { ExamPrepData, ExamPrepQuestion } from '@/services/classes-service';

/**
 * Pure question-removal helpers for the exam edit form.
 *
 * Deletion in the editor is a plain array filter, but two subtleties made it
 * worth isolating and testing: (1) the "delete all review-needed" bulk action
 * removes several questions at once, so the caller must map review state to the
 * *true* question indexes (not the filtered-view indexes) and hand them here as
 * a set; (2) an out-of-range or duplicated index must never corrupt the array.
 * These helpers return a new ``ExamPrepData`` (never mutate the argument) so the
 * React state update stays referentially safe, and ``handleSubmit`` persists the
 * shortened array to the backend, which then re-derives per-question issues.
 */

function withQuestions(
  examData: ExamPrepData,
  questions: ExamPrepQuestion[],
): ExamPrepData {
  return {
    ...examData,
    exam_prep: {
      ...examData.exam_prep,
      questions,
    },
  };
}

/** Remove a single question by its index in ``exam_prep.questions``. */
export function removeQuestionAtIndex(
  examData: ExamPrepData,
  index: number,
): ExamPrepData {
  return withQuestions(
    examData,
    examData.exam_prep.questions.filter((_question, itemIndex) => itemIndex !== index),
  );
}

/**
 * Remove every question whose index is in ``indexes``. Duplicate and
 * out-of-range indexes are ignored; the surviving questions keep their original
 * relative order. Passing an empty set returns an equivalent (new) object.
 */
export function removeQuestionsAtIndexes(
  examData: ExamPrepData,
  indexes: Iterable<number>,
): ExamPrepData {
  const removal = new Set<number>();
  for (const index of indexes) {
    if (Number.isInteger(index)) removal.add(index);
  }
  if (removal.size === 0) {
    return withQuestions(examData, [...examData.exam_prep.questions]);
  }
  return withQuestions(
    examData,
    examData.exam_prep.questions.filter((_question, itemIndex) => !removal.has(itemIndex)),
  );
}
