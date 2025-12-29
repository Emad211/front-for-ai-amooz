import { useState, useEffect } from 'react';
import { MOCK_EXAM } from '@/constants/mock/exam-data';
import { Exam, Question } from '@/types';

export const useExam = (examId: string) => {
  const [exam, setExam] = useState<Exam | null>(null);
  const [currentQuestion, setCurrentQuestion] = useState<Question | null>(null);
  const [isChatOpen, setIsChatOpen] = useState(true);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchExam = async () => {
      setIsLoading(true);
      // Simulate API call
      await new Promise((resolve) => setTimeout(resolve, 500));
      setExam(MOCK_EXAM);
      if (MOCK_EXAM.questionsList && MOCK_EXAM.questionsList.length > 0) {
        setCurrentQuestion(MOCK_EXAM.questionsList[0]);
      }
      setIsLoading(false);
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
    goToNextQuestion,
    goToPrevQuestion,
    submitAnswer,
  };
};
