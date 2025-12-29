import { Exam } from '@/types';

export const MOCK_EXAM: Exam = {
  id: '1',
  title: 'کنکور تیر 1403',
  subject: 'ریاضی',
  description: 'آزمون جامع ریاضی کنکور سراسری تیر ماه 1403',
  tags: ['کنکور', 'ریاضی', '1403'],
  questions: 11,
  totalQuestions: 11,
  currentQuestionIndex: 0,
  timeRemaining: 3600, // 60 minutes
  questionsList: [
    {
      id: 'q1',
      number: 1,
      text: 'اگر ۱, 2x - 1, x + 1, x² + x و x⁴ به ترتیب جملات چهارم، پنجم، هفتم و هشتم یک دنباله هندسی باشند، حاصل ضرب مقادیر ممکن برای قدر نسبت این دنباله کدام است؟',
      options: [
        { id: 'a', label: 'الف', text: '۱' },
        { id: 'b', label: 'ب', text: '-۱' },
        { id: 'c', label: 'ج', text: '۲' },
        { id: 'd', label: 'د', text: '-۲' },
      ],
      correctOptionId: 'c',
    },
    // Add more questions as needed
  ],
};
