import test from 'node:test';
import assert from 'node:assert/strict';
import {
  buildSourceMapMutationPayload,
  canConfirmEditableSourceMap,
  canMoveEditablePageEarlier,
  canMoveEditablePageLater,
  countUnknownPages,
  createEditableSourceMapPages,
  isCompleteEditableSourceMap,
  moveEditablePageEarlier,
  moveEditablePageLater,
  rotateEditablePageClockwise,
  sourceMapPagesEqual,
  updateEditablePageRole,
  type EditableSourceMapPage,
  type ExamPrepV4Page,
} from './source-map-model.ts';

const sourcePages: ExamPrepV4Page[] = [
  {
    pageNumber: 2,
    displayOrder: 3,
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
    displayOrder: 1,
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
    displayOrder: 2,
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

function pageByNumber(pages: EditableSourceMapPage[], pageNumber: number) {
  const page = pages.find((item) => item.pageNumber === pageNumber);
  assert.ok(page);
  return page;
}

test('creates a complete editable map sorted by virtual order', () => {
  assert.deepEqual(initialPages(), [
    { pageNumber: 1, displayOrder: 1, role: 'cover', orientation: 90 },
    { pageNumber: 3, displayOrder: 2, role: 'answer_key', orientation: 0 },
    { pageNumber: 2, displayOrder: 3, role: 'questions', orientation: 0 },
  ]);
  assert.equal(isCompleteEditableSourceMap(initialPages(), 3), true);
});

test('rejects incomplete, duplicate physical, or duplicate virtual maps', () => {
  assert.equal(isCompleteEditableSourceMap(initialPages().slice(0, 2), 3), false);
  assert.equal(
    isCompleteEditableSourceMap([
      { pageNumber: 1, displayOrder: 1, role: 'cover', orientation: 0 },
      { pageNumber: 1, displayOrder: 2, role: 'questions', orientation: 0 },
      { pageNumber: 3, displayOrder: 3, role: 'answer_key', orientation: 0 },
    ], 3),
    false,
  );
  assert.equal(
    isCompleteEditableSourceMap([
      { pageNumber: 1, displayOrder: 1, role: 'cover', orientation: 0 },
      { pageNumber: 2, displayOrder: 1, role: 'questions', orientation: 0 },
      { pageNumber: 3, displayOrder: 3, role: 'answer_key', orientation: 0 },
    ], 3),
    false,
  );
  assert.equal(
    isCompleteEditableSourceMap([
      { pageNumber: 2, displayOrder: 1, role: 'cover', orientation: 0 },
    ], 1),
    false,
  );
});

test('role edits are immutable and dirty until returned to initial value', () => {
  const initial = initialPages();
  const changed = updateEditablePageRole(initial, 2, 'ignored');
  assert.equal(pageByNumber(initial, 2).role, 'questions');
  assert.equal(pageByNumber(changed, 2).role, 'ignored');
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

  assert.equal(pageByNumber(once, 2).orientation, 90);
  assert.equal(pageByNumber(twice, 2).orientation, 180);
  assert.equal(pageByNumber(three, 2).orientation, 270);
  assert.equal(pageByNumber(four, 2).orientation, 0);
  assert.equal(sourceMapPagesEqual(initial, four), true);
});

test('move earlier swaps only adjacent virtual positions and preserves source identity', () => {
  const initial = initialPages();
  const moved = moveEditablePageEarlier(initial, 2);

  assert.deepEqual(moved.map((page) => page.pageNumber), [1, 2, 3]);
  assert.deepEqual(moved.map((page) => page.displayOrder), [1, 2, 3]);
  assert.equal(pageByNumber(moved, 2).displayOrder, 2);
  assert.equal(pageByNumber(moved, 3).displayOrder, 3);
  assert.deepEqual(
    [...moved].map((page) => page.pageNumber).sort((a, b) => a - b),
    [1, 2, 3],
  );
  assert.equal(sourceMapPagesEqual(initial, moved), false);

  const reverted = moveEditablePageLater(moved, 2);
  assert.equal(sourceMapPagesEqual(initial, reverted), true);
});

test('first and last virtual pages cannot move beyond map boundaries', () => {
  const initial = initialPages();
  assert.equal(canMoveEditablePageEarlier(initial, 1), false);
  assert.equal(canMoveEditablePageLater(initial, 2), false);
  assert.equal(canMoveEditablePageEarlier(initial, 3), true);
  assert.equal(canMoveEditablePageLater(initial, 3), true);

  assert.equal(
    sourceMapPagesEqual(initial, moveEditablePageEarlier(initial, 1)),
    true,
  );
  assert.equal(
    sourceMapPagesEqual(initial, moveEditablePageLater(initial, 2)),
    true,
  );
});

test('mutation payload sends every source page in virtual order', () => {
  const payload = buildSourceMapMutationPayload(7, [
    { pageNumber: 2, displayOrder: 3, role: 'questions', orientation: 90 },
    { pageNumber: 1, displayOrder: 1, role: 'cover', orientation: 0 },
    { pageNumber: 3, displayOrder: 2, role: 'answer_solutions', orientation: 180 },
  ]);

  assert.equal(payload.expectedRevision, 7);
  assert.deepEqual(payload.pages.map((page) => page.pageNumber), [1, 3, 2]);
  assert.deepEqual(payload.pages.map((page) => page.displayOrder), [1, 2, 3]);
  assert.deepEqual(payload.pages[1], {
    pageNumber: 3,
    displayOrder: 2,
    role: 'answer_solutions',
    orientation: 180,
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

  const dirty = moveEditablePageEarlier(initial, 2);
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
