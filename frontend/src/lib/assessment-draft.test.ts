import assert from 'node:assert/strict';
import test from 'node:test';

import {
  clearAssessmentDraft,
  createAssessmentDraftKey,
  createAssessmentVersion,
  loadAssessmentDraft,
  saveAssessmentDraft,
  type AssessmentDraftStorage,
} from './assessment-draft';

function memoryStorage(): AssessmentDraftStorage {
  const values = new Map<string, string>();
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key),
  };
}

test('restores only answers belonging to the same assessment version', () => {
  const storage = memoryStorage();
  const key = createAssessmentDraftKey({
    ownerId: 'student-1',
    courseId: '12',
    assessmentType: 'chapter-quiz',
    chapterId: 'chapter-3',
  });
  const version = createAssessmentVersion(7, ['q1', 'q2']);

  saveAssessmentDraft(storage, key, version, { q1: 'الف', q2: '', stale: 'نباید برگردد' });

  assert.deepEqual(loadAssessmentDraft(storage, key, version, ['q1', 'q2']), { q1: 'الف' });
  assert.equal(
    loadAssessmentDraft(storage, key, createAssessmentVersion(7, ['new-q']), ['new-q']),
    null,
  );
});

test('isolates drafts by student and assessment scope', () => {
  const first = createAssessmentDraftKey({
    ownerId: 'student-1',
    courseId: '12',
    assessmentType: 'final-exam',
  });
  const second = createAssessmentDraftKey({
    ownerId: 'student-2',
    courseId: '12',
    assessmentType: 'final-exam',
  });

  assert.notEqual(first, second);
});

test('removes empty, malformed, and explicitly cleared drafts', () => {
  const storage = memoryStorage();
  const key = 'draft';
  const version = createAssessmentVersion(1, ['q1']);

  saveAssessmentDraft(storage, key, version, { q1: '' });
  assert.equal(storage.getItem(key), null);

  storage.setItem(key, '{not-json');
  assert.equal(loadAssessmentDraft(storage, key, version, ['q1']), null);
  assert.equal(storage.getItem(key), null);

  saveAssessmentDraft(storage, key, version, { q1: 'پاسخ' });
  clearAssessmentDraft(storage, key);
  assert.equal(storage.getItem(key), null);
});

test('storage failures never block answering or reset actions', () => {
  const unavailable: AssessmentDraftStorage = {
    getItem: () => {
      throw new Error('unavailable');
    },
    setItem: () => {
      throw new Error('quota exceeded');
    },
    removeItem: () => {
      throw new Error('unavailable');
    },
  };

  assert.doesNotThrow(() =>
    saveAssessmentDraft(unavailable, 'draft', 'version', { q1: 'پاسخ' }),
  );
  assert.doesNotThrow(() => clearAssessmentDraft(unavailable, 'draft'));
  assert.equal(loadAssessmentDraft(unavailable, 'draft', 'version', ['q1']), null);
});
