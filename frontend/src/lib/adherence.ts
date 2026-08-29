/**
 * Adherence display helpers (Advisor-MVP step 8).
 *
 * The backend sends a rounded integer percent (0..100) or `null` when nothing
 * has elapsed yet. Locked color thresholds: ≥80 green / 50–79 amber / <50 red;
 * null/absent renders neutral muted (quiet-null — never a fake 0%).
 */
import { formatPersianPercent, toPersianDigits } from '@/lib/persian-digits';

/** Tailwind classes for an adherence chip/badge, by threshold. Translucent
 * tints + border match the repo's colored-badge convention. */
export function adherenceColorClass(
  percent: number | null | undefined,
): string {
  if (percent === null || percent === undefined || Number.isNaN(percent)) {
    return 'bg-muted text-muted-foreground';
  }
  if (percent >= 80) {
    return 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-500/20';
  }
  if (percent >= 50) {
    return 'bg-amber-500/10 text-amber-700 dark:text-amber-400 border border-amber-500/20';
  }
  return 'bg-red-500/10 text-red-700 dark:text-red-400 border border-red-500/20';
}

/** «۷۲٪» — integer Persian digits + Persian percent sign; '' for null so
 * callers can quiet-null render without re-checking. */
export function formatAdherence(percent: number | null | undefined): string {
  if (percent === null || percent === undefined || Number.isNaN(percent)) {
    return '';
  }
  return formatPersianPercent(percent);
}

/** Mood average as 1-decimal Persian («۳٫۷») with the Persian decimal
 * separator U+066B; '' for null. */
export function formatMoodAverage(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return '';
  }
  return toPersianDigits(value.toFixed(1).replace('.', '٫'));
}
