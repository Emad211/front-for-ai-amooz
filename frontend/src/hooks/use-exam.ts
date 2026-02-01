import { useState, useEffect, useRef } from 'react';
import { DashboardService } from '@/services/dashboard-service';
import { Exam, Question } from '@/types';

type ExamService = {
  getExam: (examId: string) => Promise<Exam>;
  submitExamPrep: (examId: string, payload: { answers: Record<string, string>; finalize?: boolean }) => Promise<{
    score_0_100: number;
    correct_count: number;
    total_questions: number;
    finalized: boolean;
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

  const submitAnswer = async (questionId: string, answerId: string) => {
    // Selection should be local-only.
    // We only send answers to backend when the user explicitly finalizes the exam.
    if (isFinalized) return;
    answersRef.current = { ...answersRef.current, [questionId]: answerId };
    setAnswers(answersRef.current);
  };

  const finalizeExam = async () => {
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
  };

  return {
    exam,
    currentQuestion,
    isChatOpen,
    toggleChat,
    isLoading,
    error,
    isSubmitting,
    isFinalized,
    answers,
    goToNextQuestion,
    goToPrevQuestion,
    submitAnswer,
    finalizeExam,
  };
};
