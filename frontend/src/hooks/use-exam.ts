import { useState, useEffect } from 'react';
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
  const [isSubmitting, setIsSubmitting] = useState(false);

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
    if (!examId) return;
    const next = { ...answers, [questionId]: answerId };
    setAnswers(next);
    setIsSubmitting(true);
    try {
      await service.submitExamPrep(examId, { answers: next, finalize: false });
    } catch (err) {
      console.error(err);
    } finally {
      setIsSubmitting(false);
    }
  };

  const finalizeExam = async () => {
    if (!examId) return;
    setIsSubmitting(true);
    try {
      await service.submitExamPrep(examId, { answers, finalize: true });
    } catch (err) {
      console.error(err);
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
    goToNextQuestion,
    goToPrevQuestion,
    submitAnswer,
    finalizeExam,
  };
};
