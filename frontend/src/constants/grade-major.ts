/**
 * National-curriculum grade/major option lists (student onboarding + profile).
 *
 * Mirrors the backend `accounts.StudentProfile` choices contract:
 * - Grade codes are zero-padded 2-char strings '01'..'12' (max_length=2 — never widen).
 * - Grades '10'..'12' keep their legacy codes and labels unchanged.
 * - `major` is REQUIRED exactly when grade ∈ MAJOR_REQUIRED_GRADES; for every
 *   other grade the major field is hidden/cleared and sent as null/omitted.
 * - عمومی (general) is a catalog axis only — it is never a user choice.
 */

export type GradeOption = { value: string; label: string };
export type MajorOption = { value: string; label: string };

/** All selectable grades, national curriculum '01'..'12'. */
export const GRADE_OPTIONS: GradeOption[] = [
  { value: '01', label: 'پایه اول' },
  { value: '02', label: 'پایه دوم' },
  { value: '03', label: 'پایه سوم' },
  { value: '04', label: 'پایه چهارم' },
  { value: '05', label: 'پایه پنجم' },
  { value: '06', label: 'پایه ششم' },
  { value: '07', label: 'پایه هفتم' },
  { value: '08', label: 'پایه هشتم' },
  { value: '09', label: 'پایه نهم' },
  // Legacy codes/labels — intentionally unchanged.
  { value: '10', label: 'دهم' },
  { value: '11', label: 'یازدهم' },
  { value: '12', label: 'دوازدهم' },
];

/** Selectable majors. عمومی is never offered as a choice. */
export const MAJOR_OPTIONS: MajorOption[] = [
  { value: 'math', label: 'ریاضی فیزیک' },
  { value: 'science', label: 'علوم تجربی' },
  { value: 'humanities', label: 'علوم انسانی' },
  { value: 'theology', label: 'علوم و معارف اسلامی' },
  { value: 'technical', label: 'فنی و حرفه‌ای و کاردانش' },
];

/** Grades of the theoretical cycle (دهم تا دوازدهم) where a major is mandatory. */
export const MAJOR_REQUIRED_GRADES: readonly string[] = ['10', '11', '12'];

/** Backend error copy — must stay verbatim in sync with the backend message. */
export const MAJOR_REQUIRED_MESSAGE =
  'برای پایه‌های دهم تا دوازدهم انتخاب رشته الزامی است.';

/** True when the given grade code requires a major ('10'|'11'|'12'). */
export function isMajorRequiredGrade(grade?: string | null): boolean {
  return !!grade && MAJOR_REQUIRED_GRADES.includes(grade);
}
