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
      numberingSystem: 'latn', 
    }).format(date);
  } catch (error) {
    console.error('Date formatting error:', error);
    return 'خطا در تاریخ';
  }
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
      numberingSystem: 'latn',
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
      numberingSystem: 'latn',
    }).format(date);
  } catch (error) {
    console.error('Date formatting error:', error);
    return 'خطا در تاریخ';
  }
}
