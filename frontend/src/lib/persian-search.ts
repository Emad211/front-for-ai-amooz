/**
 * Search-time folding for Persian text.
 *
 * Distinct from the backend's `normalize_subject_name`, and deliberately so:
 * that one is a *uniqueness key* (it must never collide two real subjects),
 * this one is a *match key* for a client-side filter (it should be generous —
 * a near-miss that hides the row the advisor is looking for is the failure
 * mode here, not an over-eager match).
 *
 * The classes it folds are the ones that arrive by accident, not by intent:
 * Arabic letterforms pasted from a PDF or an Arabic keyboard, three kinds of
 * digit, and the ZWNJ/space ambiguity in compound words («زیست‌شناسی» vs
 * «زیست شناسی» vs «زیستشناسی»).
 */

const PERSIAN_DIGITS = '۰۱۲۳۴۵۶۷۸۹';
const ARABIC_DIGITS = '٠١٢٣٤٥٦٧٨٩';

// Arabic → Persian letter equivalents. Keys are single code points.
const LETTER_FOLD: Record<string, string> = {
  'ك': 'ک',
  'ي': 'ی', 'ى': 'ی', 'ئ': 'ی',
  'ة': 'ه', 'ۀ': 'ه', 'ە': 'ه',
  'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ٱ': 'ا',
  'ؤ': 'و',
};

// Tatweel, tashkeel (harakat), superscript alef, zero-width + bidi controls, BOM.
// Escapes, not literals: these characters are invisible in an editor, so a
// future edit could delete one and nobody would see it happen.
const STRIP_RE = /[ـً-ٰٕ​-‏‪-‮﻿]/g;

/**
 * Reduce `value` to a comparable form: NFKC, Arabic→Persian letters, all digits
 * to ASCII, decorations removed, every space collapsed away, case-folded.
 *
 * Whitespace is *removed* rather than collapsed to one space so that a query
 * typed without the ZWNJ still matches a name that has one.
 */
export function foldForSearch(value: string | null | undefined): string {
  if (value === null || value === undefined) return '';
  return String(value)
    .normalize('NFKC')
    .replace(/[كيىئةۀەأإآٱؤ]/g, (ch) => LETTER_FOLD[ch] ?? ch)
    .replace(/[۰-۹]/g, (d) => String(PERSIAN_DIGITS.indexOf(d)))
    .replace(/[٠-٩]/g, (d) => String(ARABIC_DIGITS.indexOf(d)))
    .replace(STRIP_RE, '')
    .replace(/\s+/g, '')
    .toLowerCase();
}

/**
 * True when `query` is a substring of `haystack` after folding both.
 * An empty query matches everything, so a filter can call this unconditionally.
 */
export function matchesSearch(
  haystack: string | null | undefined,
  query: string | null | undefined,
): boolean {
  const needle = foldForSearch(query);
  if (!needle) return true;
  return foldForSearch(haystack).includes(needle);
}
