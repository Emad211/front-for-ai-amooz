export const TEACHER_PRODUCT_ASSETS = {
  classOverview: {
    src: '/landing/laptop-teacher-dark.png',
    replacement: 'teacher-class-overview.png',
    alt: 'نمای کلی کلاس و مراحل تولید محتوای آموزشی',
  },
  examPrep: {
    src: '/landing/exam-builder-dark.png',
    replacement: 'teacher-exam-prep.png',
    alt: 'ساخت آمادگی آزمون با هوش مصنوعی',
  },
  exercise: {
    src: '/landing/quiz-sim-dark.png',
    replacement: 'teacher-exercise-creation.png',
    alt: 'ساخت تمرین و تنظیم دستیار هوشمند',
  },
  analytics: {
    src: '/landing/mac-studio-dark.png',
    replacement: 'teacher-analytics.png',
    alt: 'داشبورد آمار و تحلیل معلم',
  },
} as const;

/**
 * `src` values are stable repository fallbacks. The supplied real teacher
 * screenshots replace them under the `replacement` filenames after the final
 * non-generative crop/export pass. Keeping the mapping centralized prevents
 * temporary Adobe URLs or duplicated asset decisions from leaking into UI code.
 */
