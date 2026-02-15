import { useState, useEffect, useRef, useCallback } from 'react';
import { DashboardService } from '@/services/dashboard-service';
import { Exam, Question } from '@/types';

/** Feedback returned after checking a single answer. */
export interface QuestionFeedback {
  isCorrect: boolean;
  attempts: number;
  hint: string;
  encouragement: string;
  scoreForQuestion: number;
}

type ExamService = {
  getExam: (examId: string) => Promise<Exam>;
  submitExamPrep: (examId: string, payload: { answers: Record<string, string>; finalize?: boolean }) => Promise<{
    score_0_100: number;
    correct_count: number;
    total_questions: number;
    finalized: boolean;
  }>;
  checkExamPrepAnswer: (examId: string, questionId: string, answer: string) => Promise<{
    is_correct: boolean;
    attempts: number;
    hint: string;
    encouragement: string;
    score_for_question: number;
  }>;
};

export const useExam = (examId?: string, service: ExamService = DashboardService) => {
  const [exam, setExam] = useState<Exam | null>(null);
  const [currentQuestion, setCurrentQuestion] = useState<Question | null>(null);
  const [isChatOpen, setIsChatOpen] = useState(true);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const answersRef = useRef<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isFinalized, setIsFinalized] = useState(false);
  const [isCheckingAnswer, setIsCheckingAnswer] = useState(false);

  // Per-question feedback state: { [questionId]: QuestionFeedback }
  const [feedbacks, setFeedbacks] = useState<Record<string, QuestionFeedback>>({});

  useEffect(() => {
    const fetchExam = async () => {
      try {
        if (!examId) {
          setExam(null);
          setCurrentQuestion(null);
          setIsLoading(false);
          return;
        }
        setIsLoading(true);
        setError(null);
        const data = await service.getExam(examId);
        setExam(data);
        if (data.questionsList && data.questionsList.length > 0) {
          setCurrentQuestion(data.questionsList[0]);
        } else {
          setCurrentQuestion(null);
        }
        setAnswers({});
        answersRef.current = {};
        setIsFinalized(false);
        setFeedbacks({});
      } catch (err) {
        console.error(err);
        setError('خطا در دریافت اطلاعات آزمون');
      } finally {
        setIsLoading(false);
      }
    };

    fetchExam();
  }, [examId, service]);

  const toggleChat = () => setIsChatOpen(!isChatOpen);

  const goToNextQuestion = () => {
    if (!exam || !currentQuestion || !exam.questionsList) return;
    const currentIndex = exam.questionsList.findIndex(q => q.id === currentQuestion.id);
    if (currentIndex < exam.questionsList.length - 1) {
      setCurrentQuestion(exam.questionsList[currentIndex + 1]);
    }
  };

  const goToPrevQuestion = () => {
    if (!exam || !currentQuestion || !exam.questionsList) return;
    const currentIndex = exam.questionsList.findIndex(q => q.id === currentQuestion.id);
    if (currentIndex > 0) {
      setCurrentQuestion(exam.questionsList[currentIndex - 1]);
    }
  };

  /** Update local answer selection (no network call). */
  const submitAnswer = useCallback(async (questionId: string, answerId: string) => {
    if (isFinalized) return;
    // Don't allow changing answer if already correct
    const fb = feedbacks[questionId];
    if (fb?.isCorrect) return;
    answersRef.current = { ...answersRef.current, [questionId]: answerId };
    setAnswers(prev => ({ ...prev, [questionId]: answerId }));
  }, [isFinalized, feedbacks]);

  /** Submit a single question answer for checking and get feedback. */
  const checkAnswer = useCallback(async (questionId: string): Promise<QuestionFeedback | null> => {
    if (!examId || isFinalized || isCheckingAnswer) return null;
    const answer = answersRef.current[questionId];
    if (!answer?.trim()) return null;

    // Don't re-check if already correct
    const existing = feedbacks[questionId];
    if (existing?.isCorrect) return existing;

    setIsCheckingAnswer(true);
    try {
      const result = await service.checkExamPrepAnswer(examId, questionId, answer);
      const fb: QuestionFeedback = {
        isCorrect: result.is_correct,
        attempts: result.attempts,
        hint: result.hint || '',
        encouragement: result.encouragement || '',
        scoreForQuestion: result.score_for_question,
      };
      setFeedbacks(prev => ({ ...prev, [questionId]: fb }));
      return fb;
    } catch (err) {
      console.error('Check answer failed:', err);
      return null;
    } finally {
      setIsCheckingAnswer(false);
    }
  }, [examId, isFinalized, isCheckingAnswer, feedbacks, service]);

  const finalizeExam = useCallback(async () => {
    if (!examId || isFinalized) return;
    setIsSubmitting(true);
    try {
      const result = await service.submitExamPrep(examId, { answers: answersRef.current, finalize: true });
      setIsFinalized(Boolean(result?.finalized));
      return result;
    } catch (err) {
      const message = err instanceof Error ? err.message : '';
      if (message.includes('قبلاً ثبت نهایی شده')) {
        setIsFinalized(true);
        return { score_0_100: 0, correct_count: 0, total_questions: 0, finalized: true };
      } else {
        console.error(err);
      }
    } finally {
      setIsSubmitting(false);
    }
  }, [examId, isFinalized, service]);

  return {
    exam,
    currentQuestion,
    isChatOpen,
    toggleChat,
    isLoading,
    error,
    isSubmitting,
    isFinalized,
    isCheckingAnswer,
    answers,
    feedbacks,
    goToNextQuestion,
    goToPrevQuestion,
    submitAnswer,
    checkAnswer,
    finalizeExam,
  };
};
