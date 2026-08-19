/**
 * foldForSearch() / matchesSearch() — the client-side match key for Persian text.
 *
 * Run manually (there is no `npm test` script in this app):
 *   npx tsx --test src/lib/persian-search.test.ts
 *
 * The cases below are the ones that actually happen: a subject curated by the
 * platform admin with a Persian yeh, searched by an advisor whose keyboard emits
 * the Arabic one — or the reverse. Without folding, the row the advisor is
 * looking at right now disappears the moment they type, which reads as "the
 * subject is missing", not "my search is picky".
 */
import assert from 'node:assert/strict';
import test from 'node:test';

import { foldForSearch, matchesSearch } from './persian-search';

test('Arabic and Persian letterforms fold together', () => {
  assert.equal(foldForSearch('ریاضي'), foldForSearch('ریاضی'));
  assert.equal(foldForSearch('كتاب'), foldForSearch('کتاب'));
  assert.equal(foldForSearch('مطالعة'), foldForSearch('مطالعه'));
  assert.equal(foldForSearch('أدبیات'), foldForSearch('ادبیات'));
});

test('Persian, Arabic-Indic and ASCII digits are the same number', () => {
  assert.equal(foldForSearch('ریاضی ۱'), foldForSearch('ریاضی 1'));
  assert.equal(foldForSearch('ریاضی ١'), foldForSearch('ریاضی ۱'));
});

test('spacing and ZWNJ do not change the key', () => {
  const target = foldForSearch('زیست‌شناسی');
  assert.equal(foldForSearch('زیست شناسی'), target);
  assert.equal(foldForSearch('زیستشناسی'), target);
  assert.equal(foldForSearch('  زیست‌شناسی  '), target);
});

test('invisible decorations are stripped', () => {
  assert.equal(foldForSearch('عرـبی'), foldForSearch('عربی')); // tatweel
  assert.equal(foldForSearch('عَرَبی'), foldForSearch('عربی')); // harakat
  assert.equal(foldForSearch('‏عربی'), foldForSearch('عربی')); // RLM
  assert.equal(foldForSearch('﻿عربی'), foldForSearch('عربی')); // BOM
});

test('genuinely different names keep different keys', () => {
  assert.notEqual(foldForSearch('ریاضی ۱'), foldForSearch('ریاضی ۲'));
  assert.notEqual(foldForSearch('فیزیک'), foldForSearch('شیمی'));
});

test('null and blank fold to empty', () => {
  assert.equal(foldForSearch(null), '');
  assert.equal(foldForSearch(undefined), '');
  assert.equal(foldForSearch('  ‌ '), '');
});

test('an empty query matches everything so the filter can run unconditionally', () => {
  assert.equal(matchesSearch('ریاضی ۱', ''), true);
  assert.equal(matchesSearch('ریاضی ۱', '   '), true);
  assert.equal(matchesSearch('ریاضی ۱', null), true);
});

test('matching is substring-based and fold-insensitive both ways', () => {
  assert.equal(matchesSearch('ریاضی ۱', 'ریاضي'), true);
  assert.equal(matchesSearch('ریاضي ۱', 'ریاضی'), true);
  assert.equal(matchesSearch('ریاضی ۱', '1'), true);
  assert.equal(matchesSearch('زیست‌شناسی', 'زیست شناسی'), true);
  assert.equal(matchesSearch('ریاضی ۱', 'شیمی'), false);
});

test('a null haystack never throws and never matches a real query', () => {
  assert.equal(matchesSearch(null, 'ریاضی'), false);
  assert.equal(matchesSearch(undefined, 'ریاضی'), false);
});
