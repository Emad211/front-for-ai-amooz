import test from 'node:test';
import assert from 'node:assert/strict';
import {
  buildSourceMapMutationPayload,
  canConfirmEditableSourceMap,
  countUnknownPages,
  createEditableSourceMapPages,
  isCompleteEditableSourceMap,
  rotateEditablePageClockwise,
  sourceMapPagesEqual,
  updateEditablePageRole,
  type EditableSourceMapPage,
  type ExamPrepV4Page,
} from './source-map-model.ts';

const sourcePages: ExamPrepV4Page[] = [
  {
    pageNumber: 2,
    predictedRole: 'questions',
    predictedConfidence: 0.9,
    teacherRole: null,
    effectiveRole: 'questions',
    orientation: 0,
    width: 100,
    height: 200,
    hasThumbnail: true,
    isDuplicate: false,
  },
  {
    pageNumber: 1,
    predictedRole: 'cover',
    predictedConfidence: 0.99,
    teacherRole: null,
    effectiveRole: 'cover',
    orientation: 90,
    width: 100,
    height: 200,
    hasThumbnail: true,
    isDuplicate: false,
  },
  {
    pageNumber: 3,
    predictedRole: 'answer_solutions',
    predictedConfidence: 0.88,
    teacherRole: 'answer_key',
    effectiveRole: 'answer_key',
    orientation: 0,
    width: 100,
    height: 200,
    hasThumbnail: true,
    isDuplicate: false,
  },
];

function initialPages(): EditableSourceMapPage[] {
  return createEditableSourceMapPages(sourcePages);
}

test('creates a complete sorted editable map from effective roles', () => {
  assert.deepEqual(initialPages(), [
    { pageNumber: 1, role: 'cover', orientation: 90 },
    { pageNumber: 2, role: 'questions', orientation: 0 },
    { pageNumber: 3, role: 'answer_key', orientation: 0 },
  ]);
  assert.equal(isCompleteEditableSourceMap(initialPages(), 3), true);
});

test('rejects incomplete, duplicated, or non-one-based maps', () => {
  assert.equal(isCompleteEditableSourceMap(initialPages().slice(0, 2), 3), false);
  assert.equal(
    isCompleteEditableSourceMap([
      { pageNumber: 1, role: 'cover', orientation: 0 },
      { pageNumber: 1, role: 'questions', orientation: 0 },
      { pageNumber: 3, role: 'answer_key', orientation: 0 },
    ], 3),
    false,
  );
  assert.equal(
    isCompleteEditableSourceMap([
      { pageNumber: 2, role: 'cover', orientation: 0 },
    ], 1),
    false,
  );
});

test('role edits are immutable and dirty until returned to initial value', () => {
  const initial = initialPages();
  const changed = updateEditablePageRole(initial, 2, 'ignored');
  assert.equal(initial[1].role, 'questions');
  assert.equal(changed[1].role, 'ignored');
  assert.equal(sourceMapPagesEqual(initial, changed), false);

  const reverted = updateEditablePageRole(changed, 2, 'questions');
  assert.equal(sourceMapPagesEqual(initial, reverted), true);
});

test('clockwise rotation cycles through the four allowed orientations', () => {
  const initial = initialPages();
  const once = rotateEditablePageClockwise(initial, 2);
  const twice = rotateEditablePageClockwise(once, 2);
  const three = rotateEditablePageClockwise(twice, 2);
  const four = rotateEditablePageClockwise(three, 2);

  assert.equal(once[1].orientation, 90);
  assert.equal(twice[1].orientation, 180);
  assert.equal(three[1].orientation, 270);
  assert.equal(four[1].orientation, 0);
  assert.equal(sourceMapPagesEqual(initial, four), true);
});

test('mutation payload always sends the complete map in page order', () => {
  const payload = buildSourceMapMutationPayload(7, [
    { pageNumber: 3, role: 'answer_solutions', orientation: 180 },
    { pageNumber: 1, role: 'cover', orientation: 0 },
    { pageNumber: 2, role: 'questions', orientation: 90 },
  ]);

  assert.equal(payload.expectedRevision, 7);
  assert.deepEqual(payload.pages.map((page) => page.pageNumber), [1, 2, 3]);
  assert.deepEqual(payload.pages[1], {
    pageNumber: 2,
    role: 'questions',
    orientation: 90,
  });
});

test('confirmation requires a clean complete known map and a SHA-256 fingerprint', () => {
  const initial = initialPages();
  const validFingerprint = 'a'.repeat(64);

  assert.equal(canConfirmEditableSourceMap({
    pages: initial,
    initialPages: initial,
    pageCount: 3,
    fingerprint: validFingerprint,
    isSaving: false,
    isConfirming: false,
    isConfirmed: false,
  }), true);

  const dirty = updateEditablePageRole(initial, 2, 'ignored');
  assert.equal(canConfirmEditableSourceMap({
    pages: dirty,
    initialPages: initial,
    pageCount: 3,
    fingerprint: validFingerprint,
    isSaving: false,
    isConfirming: false,
    isConfirmed: false,
  }), false);

  const unknown = updateEditablePageRole(initial, 2, 'unknown');
  assert.equal(countUnknownPages(unknown), 1);
  assert.equal(canConfirmEditableSourceMap({
    pages: unknown,
    initialPages: unknown,
    pageCount: 3,
    fingerprint: validFingerprint,
    isSaving: false,
    isConfirming: false,
    isConfirmed: false,
  }), false);

  assert.equal(canConfirmEditableSourceMap({
    pages: initial,
    initialPages: initial,
    pageCount: 3,
    fingerprint: '',
    isSaving: false,
    isConfirming: false,
    isConfirmed: false,
  }), false);
  assert.equal(canConfirmEditableSourceMap({
    pages: initial,
    initialPages: initial,
    pageCount: 3,
    fingerprint: validFingerprint,
    isSaving: false,
    isConfirming: false,
    isConfirmed: true,
  }), false);
});
