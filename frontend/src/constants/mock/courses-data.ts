/**
 * =============================================================================
 * COURSES MOCK DATA - داده‌های آزمایشی دوره‌ها و کلاس‌ها
 * =============================================================================
 * 
 * در این سیستم، "دوره" (Course) و "کلاس" (Class) به یک موجودیت اشاره دارند.
 * برای اتصال به Backend:
 * GET /api/courses
 * GET /api/courses/:id
 * 
 * =============================================================================
 */

import { Course } from "@/types";

export const MOCK_COURSES: Course[] = [
  {
    id: '1',
    title: "رسم نمودار توابع درجه دوم (سهمی)",
    description: "یادگیری چگونگی رسم دقیق نمودارهای توابع درجه دوم (سهمی) و تفسیر ویژگی‌های کلیدی آن‌ها.",
    tags: ["ریاضیات"],
    instructor: "دکتر علوی",
    progress: 65,
    image: "https://picsum.photos/seed/math/400/250",
    studentsCount: 24,
    lessonsCount: 12,
    status: 'active',
    createdAt: '2024-01-15',
    lastActivity: '2024-01-20',
    category: 'ریاضی',
    level: 'پیشرفته',
    rating: 4.8,
    reviews: 15,
  },
  {
    id: '2',
    title: "یادگیری ماشین: مفاهیم پایه",
    description: "آشنایی کامل با مفاهیم یادگیری نظارت شده و بدون نظارت. شروع مسیر شغلی در دنیای داده‌ها با پروژه‌های عملی.",
    tags: ["هوش مصنوعی"],
    instructor: "مهندس رضایی",
    progress: 30,
    image: "https://picsum.photos/seed/ai/400/250",
    studentsCount: 45,
    lessonsCount: 20,
    status: 'active',
    createdAt: '2024-01-10',
    lastActivity: '2024-01-22',
    category: 'هوش مصنوعی',
    level: 'متوسط',
    rating: 4.9,
    reviews: 28,
  },
  {
    id: '3',
    title: "مکانیک کوانتومی ۱",
    description: "بررسی مفاهیم بنیادی مکانیک کوانتومی، اصل عدم قطعیت هایزنبرگ و معادله شرودینگر در فضاهای یک بعدی.",
    tags: ["فیزیک"],
    instructor: "دکتر حسینی",
    progress: 10,
    image: "https://picsum.photos/seed/physics/400/250",
    studentsCount: 18,
    lessonsCount: 8,
    status: 'draft',
    createdAt: '2024-01-18',
    lastActivity: '2024-01-19',
    category: 'فیزیک',
    level: 'مبتدی',
    rating: 4.5,
    reviews: 8,
  },
  {
    id: '4',
    title: "توسعه وب با React",
    description: "ساخت اپلیکیشن‌های تک‌صفحه‌ای مدرن (SPA) با استفاده از کتابخانه React.js و مدیریت وضعیت با Redux.",
    tags: ["برنامه‌نویسی"],
    instructor: "مهندس کریمی",
    progress: 85,
    image: "https://picsum.photos/seed/web/400/250",
    studentsCount: 32,
    lessonsCount: 15,
    status: 'active',
    createdAt: '2024-01-05',
    lastActivity: '2024-01-21',
    category: 'برنامه‌نویسی',
    level: 'متوسط',
    rating: 4.7,
    reviews: 22,
  },
  {
    id: '5',
    title: "انگلیسی تخصصی مهندسی",
    description: "تقویت مهارت‌های خواندن و درک مطلب متون فنی و مهندسی. نوشتن مقالات علمی و مکاتبات رسمی.",
    tags: ["زبان"],
    instructor: "خانم جاوید",
    progress: 45,
    image: "https://picsum.photos/seed/english/400/250",
    studentsCount: 67,
    lessonsCount: 25,
    status: 'paused',
    createdAt: '2023-12-20',
    lastActivity: '2024-01-15',
    category: 'زبان',
    level: 'مبتدی',
    rating: 4.6,
    reviews: 41,
  },
  {
    id: '6',
    title: "تحلیل شعر معاصر",
    description: "نگاهی به جریان‌های شعری معاصر ایران از نیما یوشیج تا امروز. بررسی ساختار و محتوای اشعار نو.",
    tags: ["ادبیات"],
    instructor: "استاد راد",
    progress: 0,
    image: "https://picsum.photos/seed/literature/400/250",
    studentsCount: 12,
    lessonsCount: 10,
    status: 'active',
    createdAt: '2024-01-01',
    lastActivity: '2024-01-25',
    category: 'ادبیات',
    level: 'متوسط',
    rating: 4.8,
    reviews: 14,
  }
];


