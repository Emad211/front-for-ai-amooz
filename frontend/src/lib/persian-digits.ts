/**
 * Persian (Farsi) numeral + number-formatting helpers.
 *
 * The whole product UI is Persian/RTL, so every USER-FACING number (counts,
 * scores, percentages, progress, durations, IDs, chart axes/tooltips) must
 * render with Persian digits (۰۱۲۳۴۵۶۷۸۹), not Latin (0123456789). This module
 * is the single source of truth — import these instead of re-implementing the
 * replace each time (the historical private copy lived in `admin-service.ts`).
 *
 * Use Persian `٪` (U+066A) rather than ASCII `%` for percentages.
 */

const PERSIAN_DIGITS = '۰۱۲۳۴۵۶۷۸۹';
const ARABIC_DIGITS = '٠١٢٣٤٥٦٧٨٩';

/**
 * Convert every ASCII digit in `value` to its Persian counterpart.
 * Non-digit characters (separators, signs, units, letters) pass through.
 */
export function toPersianDigits(value: number | string | null | undefined): string {
  if (value === null || value === undefined) return '';
  return String(value).replace(/\d/g, (d) => PERSIAN_DIGITS[Number(d)]);
}

/**
 * Convert Persian (and Arabic-Indic) digits back to ASCII `0-9`.
 * Useful when parsing user input from a Persian-rendered field.
 */
export function toEnglishDigits(value: string | null | undefined): string {
  if (value === null || value === undefined) return '';
  return String(value)
    .replace(/[۰-۹]/g, (d) => String(PERSIAN_DIGITS.indexOf(d)))
    .replace(/[٠-٩]/g, (d) => String(ARABIC_DIGITS.indexOf(d)));
}

/**
 * Format an integer/decimal with grouped thousands and Persian digits.
 * e.g. 12345 -> "۱۲٬۳۴۵".
 */
export function formatPersianNumber(
  value: number | null | undefined,
  options?: Intl.NumberFormatOptions,
): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  // Group with en-US (ASCII separators) then transliterate, so the output is
  // deterministic regardless of the host ICU locale data.
  return toPersianDigits(value.toLocaleString('en-US', options));
}

/**
 * Absolute percentage with Persian digits + the Persian percent sign `٪`.
 * e.g. 73 -> "۷۳٪". Use this for progress, scores, shares.
 */
export function formatPersianPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return `${toPersianDigits(value)}٪`;
}

/**
 * Signed percentage delta with Persian digits + `٪` (for trend indicators).
 * e.g. 12 -> "+۱۲٪", -4 -> "-۴٪".
 */
export function formatPersianDelta(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  const sign = value >= 0 ? '+' : '';
  return `${toPersianDigits(sign + value)}٪`;
}
