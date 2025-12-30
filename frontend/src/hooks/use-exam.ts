import { useState, useEffect } from 'react';
import { DashboardService } from '@/services/dashboard-service';
import { Exam, Question } from '@/types';

export const useExam = (examId?: string) => {
  const [exam, setExam] = useState<Exam | null>(null);
  const [currentQuestion, setCurrentQuestion] = useState<Question | null>(null);
  const [isChatOpen, setIsChatOpen] = useState(true);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
        const data = await DashboardService.getExam(examId);
        setExam(data);
        if (data.questionsList && data.questionsList.length > 0) {
          setCurrentQuestion(data.questionsList[0]);
        } else {
          setCurrentQuestion(null);
        }
      } catch (err) {
        console.error(err);
        setError('خطا در دریافت اطلاعات آزمون');
      } finally {
        setIsLoading(false);
      }
    };

    fetchExam();
  }, [examId]);

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

  const submitAnswer = (questionId: string, answerId: string) => {
    // Logic to save answer
    console.log(`Submitted answer ${answerId} for question ${questionId}`);
  };

  return {
    exam,
    currentQuestion,
    isChatOpen,
    toggleChat,
    isLoading,
    error,
    goToNextQuestion,
    goToPrevQuestion,
    submitAnswer,
  };
};
