import assert from 'node:assert/strict';
import test from 'node:test';

import type { ExamPrepData, ExamPrepQuestion } from '@/services/classes-service';
import {
  removeQuestionAtIndex,
  removeQuestionsAtIndexes,
} from './exam-edit-mutations';

function question(id: string): ExamPrepQuestion {
  return {
    question_id: id,
    question_text_markdown: `متن ${id}`,
    options: [
      { label: 'الف', text_markdown: '۱' },
      { label: 'ب', text_markdown: '۲' },
    ],
    correct_option_label: 'الف',
    correct_option_text_markdown: '۱',
    teacher_solution_markdown: '',
    final_answer_markdown: '',
    confidence: 1,
    issues: [],
  };
}

function examData(ids: string[]): ExamPrepData {
  return {
    exam_prep: {
      title: 'آزمون',
      questions: ids.map(question),
    },
  };
}

function ids(data: ExamPrepData): string[] {
  return data.exam_prep.questions.map((item) => item.question_id ?? '');
}

test('removeQuestionAtIndex drops exactly the targeted question', () => {
  const data = examData(['a', 'b', 'c']);
  const next = removeQuestionAtIndex(data, 1);
  assert.deepEqual(ids(next), ['a', 'c']);
});

test('removeQuestionAtIndex does not mutate the original data', () => {
  const data = examData(['a', 'b', 'c']);
  removeQuestionAtIndex(data, 0);
  // The source array is untouched — React state stays referentially safe.
  assert.deepEqual(ids(data), ['a', 'b', 'c']);
});

test('removeQuestionsAtIndexes removes every listed index and keeps order', () => {
  // The literal owner workflow: delete all review-needed questions at once,
  // publish the healthy remainder. Indexes come from the review summary mapped
  // to the true question positions, not the filtered view.
  const data = examData(['a', 'b', 'c', 'd', 'e']);
  const next = removeQuestionsAtIndexes(data, [1, 3]);
  assert.deepEqual(ids(next), ['a', 'c', 'e']);
});

test('removeQuestionsAtIndexes ignores duplicate and out-of-range indexes', () => {
  const data = examData(['a', 'b', 'c']);
  const next = removeQuestionsAtIndexes(data, [1, 1, 9, -1]);
  assert.deepEqual(ids(next), ['a', 'c']);
});

test('removeQuestionsAtIndexes with an empty set returns all questions', () => {
  const data = examData(['a', 'b', 'c']);
  const next = removeQuestionsAtIndexes(data, []);
  assert.deepEqual(ids(next), ['a', 'b', 'c']);
});

test('removing every review-needed question can leave a publishable remainder', () => {
  // Questions b and d are the review-needed ones; deleting them must leave a
  // non-empty healthy set so publish (gated only by questions.length > 0) works.
  const data = examData(['a', 'b', 'c', 'd', 'e']);
  const reviewNeededIndexes = [1, 3];
  const next = removeQuestionsAtIndexes(data, reviewNeededIndexes);
  assert.equal(next.exam_prep.questions.length, 3);
  assert.deepEqual(ids(next), ['a', 'c', 'e']);
});
