/**
 * Formats a date string or object to a Solar Hijri (Persian) string.
 * Format: YYYY/MM/DD HH:mm
 */
export function formatPersianDateTime(dateInput: string | Date | number | undefined | null): string {
  if (!dateInput) return '—';
  
  try {
    const date = new Date(dateInput);
    if (isNaN(date.getTime())) return 'تاریخ نامعتبر';

    return new Intl.DateTimeFormat('fa-IR', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
      calendar: 'persian',
      numberingSystem: 'arabext',
    }).format(date);
  } catch (error) {
    console.error('Date formatting error:', error);
    return 'خطا در تاریخ';
  }
}

function parseDateInput(dateInput: string | Date | number | undefined | null): Date | null {
  if (!dateInput) return null;

  const date = new Date(dateInput);
  if (Number.isNaN(date.getTime())) return null;
  return date;
}

function pad2(value: number): string {
  return String(value).padStart(2, '0');
}

/**
 * Convert a date-like input to the local `YYYY-MM-DDTHH:mm` shape used by
 * date/time form controls. This preserves the user's local timezone instead of
 * exposing a raw UTC ISO substring.
 */
export function toLocalDateTimeValue(
  dateInput: string | Date | number | undefined | null,
): string {
  const date = parseDateInput(dateInput);
  if (!date) return '';

  return [
    date.getFullYear(),
    pad2(date.getMonth() + 1),
    pad2(date.getDate()),
  ].join('-') + `T${pad2(date.getHours())}:${pad2(date.getMinutes())}`;
}

/**
 * Formats a date string or object to a Solar Hijri (Persian) date only.
 * Format: YYYY/MM/DD
 */
export function formatPersianDate(dateInput: string | Date | number | undefined | null): string {
  if (!dateInput) return '—';
  
  try {
    const date = new Date(dateInput);
    if (isNaN(date.getTime())) return 'تاریخ نامعتبر';

    return new Intl.DateTimeFormat('fa-IR', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      calendar: 'persian',
      numberingSystem: 'arabext',
    }).format(date);
  } catch (error) {
    console.error('Date formatting error:', error);
    return 'خطا در تاریخ';
  }
}

/**
 * Formats a date to Month/Day in Persian calendar.
 */
export function formatPersianMonthDay(dateInput: string | Date | number | undefined | null): string {
  if (!dateInput) return '—';
  
  try {
    const date = new Date(dateInput);
    if (isNaN(date.getTime())) return 'تاریخ نامعتبر';

    return new Intl.DateTimeFormat('fa-IR', {
      month: '2-digit',
      day: '2-digit',
      calendar: 'persian',
      numberingSystem: 'arabext',
    }).format(date);
  } catch (error) {
    console.error('Date formatting error:', error);
    return 'خطا در تاریخ';
  }
}
