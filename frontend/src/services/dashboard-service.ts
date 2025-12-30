import { 
  MOCK_DASHBOARD_STATS, 
  MOCK_ACTIVITIES, 
  MOCK_UPCOMING_EVENTS, 
  MOCK_STUDENT_PROFILE,
  MOCK_COURSES,
  MOCK_EXAMS,
  MOCK_EXAM,
  MOCK_TICKETS,
  MOCK_NOTIFICATIONS,
  MOCK_CALENDAR_EVENTS,
  MOCK_COURSE_CONTENT,
  MOCK_LESSON_DETAIL,
} from '@/constants/mock';
import type { UserProfile } from '@/types';

/**
 * Dashboard Service
 * Handles all data fetching for the student dashboard.
 * Currently returns mock data, but ready to be replaced with API calls.
 */
export const DashboardService = {
  getStats: async () => {
    // Simulate API delay
    await new Promise(resolve => setTimeout(resolve, 500));
    return MOCK_DASHBOARD_STATS;
  },

  getActivities: async () => {
    await new Promise(resolve => setTimeout(resolve, 500));
    return MOCK_ACTIVITIES;
  },

  getUpcomingEvents: async () => {
    await new Promise(resolve => setTimeout(resolve, 500));
    return MOCK_UPCOMING_EVENTS;
  },

  getStudentProfile: async () => {
    await new Promise(resolve => setTimeout(resolve, 500));
    return MOCK_STUDENT_PROFILE;
  },

  getCourses: async () => {
    await new Promise(resolve => setTimeout(resolve, 600));
    return MOCK_COURSES;
  },

  getExams: async () => {
    await new Promise(resolve => setTimeout(resolve, 700));
    return MOCK_EXAMS;
  },

  getExam: async (examId: string) => {
    await new Promise(resolve => setTimeout(resolve, 500));

    const ensureQuestionsList = (exam: any) => {
      const desiredCount = Number(exam?.totalQuestions ?? exam?.questions ?? 0);
      const baseList = Array.isArray(exam?.questionsList) ? exam.questionsList : [];
      const baseQuestion = baseList[0] ?? {
        id: 'q1',
        number: 1,
        text: 'سوال نمونه',
        options: [
          { id: 'a', label: 'الف', text: 'گزینه ۱' },
          { id: 'b', label: 'ب', text: 'گزینه ۲' },
          { id: 'c', label: 'ج', text: 'گزینه ۳' },
          { id: 'd', label: 'د', text: 'گزینه ۴' },
        ],
        correctOptionId: 'a',
      };

      const count = Number.isFinite(desiredCount) && desiredCount > 0 ? desiredCount : (baseList.length || 1);

      const questionsList = Array.from({ length: count }, (_, idx) => {
        const n = idx + 1;
        return {
          ...baseQuestion,
          id: `q${n}`,
          number: n,
          options: baseQuestion.options?.map((o: any) => ({ ...o })) ?? [],
        };
      });

      return {
        ...exam,
        totalQuestions: count,
        questions: count,
        currentQuestionIndex: 0,
        questionsList,
      };
    };

    const fromList = MOCK_EXAMS.find(e => String(e.id) === String(examId));
    if (fromList) {
      const hydrated = {
        ...MOCK_EXAM,
        id: String(fromList.id),
        title: fromList.title,
        description: fromList.description,
        tags: fromList.tags,
        subject: fromList.tags?.[0] ?? MOCK_EXAM.subject,
        questions: fromList.questions,
        totalQuestions: fromList.questions,
      };
      return ensureQuestionsList(hydrated);
    }

    if (String(MOCK_EXAM.id) === String(examId)) {
      return ensureQuestionsList({ ...MOCK_EXAM, id: String(examId) });
    }

    // Fallback: keep the page functional even for unknown IDs
    return ensureQuestionsList({ ...MOCK_EXAM, id: String(examId || MOCK_EXAM.id) });
  },

  getTickets: async () => {
    await new Promise(resolve => setTimeout(resolve, 600));
    return MOCK_TICKETS;
  },

  getNotifications: async () => {
    await new Promise(resolve => setTimeout(resolve, 400));
    return MOCK_NOTIFICATIONS;
  },

  getCalendarEvents: async () => {
    await new Promise(resolve => setTimeout(resolve, 500));
    return MOCK_CALENDAR_EVENTS;
  },

  getCourseContent: async (courseId?: string) => {
    await new Promise(resolve => setTimeout(resolve, 800));
    return MOCK_COURSE_CONTENT;
  },

  getLessonDetail: async (lessonId: string) => {
    await new Promise(resolve => setTimeout(resolve, 500));
    return MOCK_LESSON_DETAIL;
  },

  getUserProfile: async () => {
    await new Promise(resolve => setTimeout(resolve, 500));
    return MOCK_STUDENT_PROFILE;
  },

  updateUserProfile: async (data: Partial<UserProfile>) => {
    await new Promise(resolve => setTimeout(resolve, 1000));
    return { success: true, data };
  }
};
