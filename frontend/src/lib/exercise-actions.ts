import type { StudentExerciseListItem } from '@/services/exercises-service';

export type StudentExerciseActionKind = 'start' | 'continue' | 'result' | 'answers';

export type StudentExerciseAction = {
  kind: StudentExerciseActionKind;
  label: string;
  href: string;
};

export function isExerciseWindowClosed(exercise: StudentExerciseListItem): boolean {
  return exercise.deadlinePassed && !exercise.allowLate;
}

export function getStudentExerciseActionKind(
  exercise: StudentExerciseListItem
): StudentExerciseActionKind {
  if (exercise.submissionStatus && exercise.submissionStatus !== 'draft') {
    return 'result';
  }

  if (isExerciseWindowClosed(exercise)) {
    return 'answers';
  }

  if (exercise.submissionStatus === 'draft') {
    return 'continue';
  }

  return 'start';
}

export function getStudentExerciseAction(
  exercise: StudentExerciseListItem,
  sessionId: number
): StudentExerciseAction {
  const kind = getStudentExerciseActionKind(exercise);

  if (kind === 'result') {
    return {
      kind,
      label: 'دیدن نتیجه',
      href: `/exercises/${exercise.id}/result?session=${sessionId}`,
    };
  }

  if (kind === 'answers') {
    return { kind, label: 'پاسخ‌نامه', href: '/exercises/answers' };
  }

  if (kind === 'continue') {
    return {
      kind,
      label: 'ادامه تمرین',
      href: `/exercises/${exercise.id}?session=${sessionId}`,
    };
  }

  return {
    kind,
    label: 'شروع تمرین',
    href: `/exercises/${exercise.id}?session=${sessionId}`,
  };
}

export function compareStudentExercises(a: StudentExerciseListItem, b: StudentExerciseListItem): number {
  const rank = (exercise: StudentExerciseListItem): number => {
    const kind = getStudentExerciseActionKind(exercise);
    if (kind === 'continue') return 0;
    if (kind === 'start') return 1;
    if (kind === 'result') return 2;
    return 3;
  };

  const rankDelta = rank(a) - rank(b);
  if (rankDelta !== 0) return rankDelta;

  const aDeadline = a.deadline ? Date.parse(a.deadline) : Number.POSITIVE_INFINITY;
  const bDeadline = b.deadline ? Date.parse(b.deadline) : Number.POSITIVE_INFINITY;
  if (Number.isFinite(aDeadline) || Number.isFinite(bDeadline)) {
    return aDeadline - bDeadline;
  }

  return b.id - a.id;
}

export function pickStudentExerciseActionTarget(
  exercises: StudentExerciseListItem[]
): StudentExerciseListItem | null {
  if (exercises.length === 0) return null;
  return [...exercises].sort(compareStudentExercises)[0] ?? null;
}
