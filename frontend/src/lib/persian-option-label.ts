const PERSIAN_LABELS = ['الف', 'ب', 'ج', 'د'] as const;

export function toPersianOptionLabel(label: string, optionIndex?: number): string {
  const raw = String(label ?? '').trim();
  if (!raw) {
    if (typeof optionIndex === 'number' && optionIndex >= 0 && optionIndex < PERSIAN_LABELS.length) {
      return PERSIAN_LABELS[optionIndex];
    }
    return '';
  }

  // Already Persian.
  if ((PERSIAN_LABELS as readonly string[]).includes(raw)) return raw;

  // Latin A/B/C/D.
  const upper = raw.toUpperCase();
  const map: Record<string, string> = { A: 'الف', B: 'ب', C: 'ج', D: 'د' };
  if (map[upper]) return map[upper];

  // Numeric 1..4.
  const num = Number(raw);
  if (Number.isFinite(num) && num >= 1 && num <= 4) {
    return PERSIAN_LABELS[num - 1];
  }

  // Fall back: if index is known, prefer index-based Persian labels.
  if (typeof optionIndex === 'number' && optionIndex >= 0 && optionIndex < PERSIAN_LABELS.length) {
    return PERSIAN_LABELS[optionIndex];
  }

  return raw;
}
