import '@/services/classes-service';

declare module '@/services/classes-service' {
  interface ExamPrepQuestion {
    source_question_number?: string | number;
    question_number?: string | number;
    section_key?: string;
    scope_key?: string;
    source_pages?: number[];
    source_verified?: boolean;
    teacher_reviewed_issue_codes?: string[];
  }

  interface ExamPrepExtractionIssue {
    questionNumber?: string | number;
    scopeKey?: string;
  }

  interface ExamPrepExtractionAudit {
    usableQuestionCount?: number;
    questionsNeedingReview?: number;
    failedPageNumbers?: number[];
    questionNumberGaps?: Record<string, number[]>;
  }
}
