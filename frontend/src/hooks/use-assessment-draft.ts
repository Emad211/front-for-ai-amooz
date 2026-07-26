'use client';

import React from 'react';

import {
  clearAssessmentDraft,
  createAssessmentDraftKey,
  createAssessmentVersion,
  getAssessmentDraftStorage,
  loadAssessmentDraft,
  saveAssessmentDraft,
} from '@/lib/assessment-draft';

type AssessmentDraftScope = {
  ownerId: string;
  courseId: string;
  assessmentType: 'chapter-quiz' | 'final-exam';
  chapterId?: string;
};

type AssessmentDescriptor = {
  version: string;
  questionIds: string[];
};

export function useAssessmentDraft(scope: AssessmentDraftScope) {
  const [answers, setAnswers] = React.useState<Record<string, string>>({});
  const [assessment, setAssessment] = React.useState<AssessmentDescriptor | null>(null);
  const hydratedDraftRef = React.useRef('');
  const draftKey = React.useMemo(
    () =>
      scope.ownerId
        ? createAssessmentDraftKey({
            ownerId: scope.ownerId,
            courseId: scope.courseId,
            assessmentType: scope.assessmentType,
            chapterId: scope.chapterId,
          })
        : '',
    [scope.assessmentType, scope.chapterId, scope.courseId, scope.ownerId],
  );

  const initializeAssessment = React.useCallback(
    (assessmentId: string | number, questionIds: Array<string | number>) => {
      const normalizedIds = questionIds.map((questionId) => String(questionId));
      setAssessment({
        version: createAssessmentVersion(assessmentId, normalizedIds),
        questionIds: normalizedIds,
      });
      setAnswers(Object.fromEntries(normalizedIds.map((questionId) => [questionId, ''])));
    },
    [],
  );

  React.useEffect(() => {
    if (!draftKey || !assessment) return;
    const hydrationId = `${draftKey}\u0000${assessment.version}`;
    if (hydratedDraftRef.current === hydrationId) return;
    hydratedDraftRef.current = hydrationId;

    if (Object.values(answers).some((answer) => answer.length > 0)) {
      saveAssessmentDraft(
        getAssessmentDraftStorage(),
        draftKey,
        assessment.version,
        answers,
      );
      return;
    }

    const restored = loadAssessmentDraft(
      getAssessmentDraftStorage(),
      draftKey,
      assessment.version,
      assessment.questionIds,
    );
    if (restored) {
      setAnswers((current) => ({ ...current, ...restored }));
    }
  }, [answers, assessment, draftKey]);

  const updateAnswer = React.useCallback(
    (questionId: string, answer: string) => {
      setAnswers((current) => {
        const next = { ...current, [questionId]: answer };
        if (assessment) {
          saveAssessmentDraft(
            getAssessmentDraftStorage(),
            draftKey,
            assessment.version,
            next,
          );
        }
        return next;
      });
    },
    [assessment, draftKey],
  );

  const clearDraft = React.useCallback(() => {
    clearAssessmentDraft(getAssessmentDraftStorage(), draftKey);
  }, [draftKey]);

  return {
    answers,
    initializeAssessment,
    updateAnswer,
    clearDraft,
  };
}
