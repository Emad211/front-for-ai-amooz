const DIGIT_MAP: Record<string, string> = {
  '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4',
  '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9',
  '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
  '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9',
};

function asciiDigits(raw: string): string {
  return Array.from(String(raw ?? ''))
    .map((char) => DIGIT_MAP[char] ?? char)
    .filter((char) => /[0-9]/.test(char))
    .join('');
}

export function normalizeIranPhone(raw: string): string {
  let digits = asciiDigits(raw);
  if (digits.startsWith('98') && digits.length === 12) digits = `0${digits.slice(2)}`;
  if (digits.length === 10 && digits.startsWith('9')) digits = `0${digits}`;
  return digits;
}

export function sanitizeIranPhoneInput(raw: string): string {
  const digits = asciiDigits(raw);
  if (digits.startsWith('98')) {
    return digits.length === 12 ? normalizeIranPhone(digits) : digits.slice(0, 12);
  }
  return normalizeIranPhone(digits).slice(0, 11);
}

export function isValidIranPhone(value: string): boolean {
  return /^09\d{9}$/.test(value);
}
