/**
 * =============================================================================
 * COURSE CONTENT MOCK DATA - داده‌های آزمایشی محتوای دوره
 * =============================================================================
 */

export interface Lesson {
  id: string;
  title: string;
  type: 'video' | 'text' | 'quiz';
  duration?: string;
  isCompleted?: boolean;
  isActive?: boolean;
  isLocked?: boolean;
  isSpecial?: boolean;
}

export interface Chapter {
  id: string;
  title: string;
  lessons: Lesson[];
}

export interface CourseContent {
  id: string;
  title: string;
  description: string;
  progress: number;
  level: string;
  duration: string;
  chapters: Chapter[];
}

export const MOCK_COURSE_CONTENT: CourseContent = {
  id: 'course-1',
  title: 'رسم نمودار توابع درجه دوم (سهمی)',
  description: 'یادگیری چگونگی رسم دقیق نمودارهای توابع درجه دوم (سهمی) و تفسیر ویژگی‌های کلیدی آن‌ها.',
  progress: 67,
  level: 'مبتدی',
  duration: '۳۰-۴۵ دقیقه',
  chapters: [
    {
      id: 'chapter-1',
      title: 'آشنایی با سهمی',
      lessons: [
        { id: 'l1', title: 'شکل کلی و جهت سهمی', type: 'text' },
        { id: 'l2', title: 'رأس سهمی: مهمترین نقطه', type: 'video', duration: '10:00', isActive: true },
        { id: 'l3', title: 'ارتباط رأس با نقاط متقارن', type: 'text' },
        { id: 'l4', title: 'عرض از مبدأ و ریشه‌ها', type: 'text' },
        { id: 'l5', title: 'آزمون فصل', type: 'quiz', isSpecial: true },
      ]
    },
    {
      id: 'chapter-2',
      title: 'گام به گام رسم نمودار',
      lessons: [
        { id: 'l6', title: 'مثال عملی رسم سهمی با a>0', type: 'text' },
        { id: 'l7', title: 'مثال عملی رسم سهمی با a<0', type: 'text' },
        { id: 'l8', title: 'آزمون فصل', type: 'quiz', isSpecial: true },
      ]
    }
  ]
};

export const MOCK_LESSON_DETAIL = {
  id: 'l2',
  title: 'رأس سهمی: مهمترین نقطه',
  content: `
    رأس سهمی (Vertex) نقطه‌ای است که در آن سهمی تغییر جهت می‌دهد. این نقطه در واقع بحرانی‌ترین بخش یک سهمی است، زیرا تعیین‌کننده مقدار مینیمم یا ماکزیمم تابع درجه دوم می‌باشد.
    
    ### ویژگی‌های مهم رأس سهمی:
    - اگر a > 0 باشد، دهانه سهمی رو به بالاست و رأس سهمی نقطه مینیمم است.
    - اگر a < 0 باشد، دهانه سهمی رو به پایین است و رأس سهمی نقطه ماکزیمم است.
    - خط تقارن سهمی همواره یک خط عمودی است که از رأس سهمی می‌گذرد (x = -b/2a).
  `,
  formulas: [
    { label: 'طول رأس سهمی (x)', formula: 'x = -b / 2a' },
    { label: 'عرض رأس سهمی (y)', formula: 'y = f(-b / 2a)' },
  ],
  tips: [
    'نکته کنکوری: در مسائل بهینه‌سازی، هرگاه صحبت از بیشترین یا کمترین مقدار یک تابع درجه دوم باشد، هدف یافتن عرض رأس سهمی است.'
  ]
};
