/**
 * =============================================================================
 * STUDENTS MOCK DATA - داده‌های آزمایشی دانش‌آموزان
 * =============================================================================
 * 
 * برای اتصال به Backend:
 * این داده‌ها را با API call به endpoint زیر جایگزین کنید:
 * GET /api/students
 * GET /api/students/:id
 * 
 * =============================================================================
 */

import { Student } from "@/types";

export interface StudentSimple {
  id: string;
  name: string;
  email: string;
  avatar?: string;
}

export const MOCK_STUDENTS: Student[] = [
  {
    id: '1',
    name: 'علی احمدی',
    email: 'ali.ahmadi@example.com',
    phone: '09121234567',
    avatar: 'https://picsum.photos/seed/student1/100/100',
    enrolledClasses: 3,
    completedLessons: 24,
    totalLessons: 45,
    averageScore: 85,
    status: 'active',
    joinDate: '2024-01-10',
    lastActivity: '2024-01-22',
    performance: 'excellent',
  },
  {
    id: '2',
    name: 'زهرا محمدی',
    email: 'zahra.mohammadi@example.com',
    phone: '09129876543',
    avatar: 'https://picsum.photos/seed/student2/100/100',
    enrolledClasses: 5,
    completedLessons: 67,
    totalLessons: 90,
    averageScore: 92,
    status: 'active',
    joinDate: '2023-12-15',
    lastActivity: '2024-01-23',
    performance: 'excellent',
  },
  {
    id: '3',
    name: 'محمد رضایی',
    email: 'mohammad.rezaei@example.com',
    phone: '09135551234',
    avatar: 'https://picsum.photos/seed/student3/100/100',
    enrolledClasses: 2,
    completedLessons: 15,
    totalLessons: 30,
    averageScore: 72,
    status: 'active',
    joinDate: '2024-01-18',
    lastActivity: '2024-01-21',
    performance: 'good',
  },
  {
    id: '4',
    name: 'فاطمه کریمی',
    email: 'fatemeh.karimi@example.com',
    phone: '09141239876',
    avatar: 'https://picsum.photos/seed/student4/100/100',
    enrolledClasses: 4,
    completedLessons: 38,
    totalLessons: 60,
    averageScore: 78,
    status: 'active',
    joinDate: '2024-01-05',
    lastActivity: '2024-01-20',
    performance: 'good',
  },
  {
    id: '5',
    name: 'حسین نوری',
    email: 'hossein.noori@example.com',
    phone: '09151234567',
    avatar: 'https://picsum.photos/seed/student5/100/100',
    enrolledClasses: 2,
    completedLessons: 8,
    totalLessons: 30,
    averageScore: 58,
    status: 'inactive',
    joinDate: '2023-12-20',
    lastActivity: '2024-01-10',
    performance: 'needs-improvement',
  },
  {
    id: '6',
    name: 'مریم صادقی',
    email: 'maryam.sadeghi@example.com',
    phone: '09161234567',
    avatar: 'https://picsum.photos/seed/student6/100/100',
    enrolledClasses: 6,
    completedLessons: 89,
    totalLessons: 100,
    averageScore: 95,
    status: 'active',
    joinDate: '2023-11-10',
    lastActivity: '2024-01-23',
    performance: 'excellent',
  },
  {
    id: '7',
    name: 'امیر رضایی',
    email: 'amir.rezaei@example.com',
    phone: '09171234567',
    avatar: 'https://picsum.photos/seed/student7/100/100',
    enrolledClasses: 3,
    completedLessons: 28,
    totalLessons: 45,
    averageScore: 81,
    status: 'active',
    joinDate: '2024-01-12',
    lastActivity: '2024-01-23',
    performance: 'good',
  },
  {
    id: '8',
    name: 'سارا حسینی',
    email: 'sara.hosseini@example.com',
    phone: '09181234567',
    avatar: 'https://picsum.photos/seed/student8/100/100',
    enrolledClasses: 4,
    completedLessons: 52,
    totalLessons: 60,
    averageScore: 88,
    status: 'active',
    joinDate: '2023-12-01',
    lastActivity: '2024-01-22',
    performance: 'excellent',
  },
];

// لیست ساده دانش‌آموزان برای انتخاب در فرم‌ها
export const MOCK_STUDENTS_SIMPLE: StudentSimple[] = MOCK_STUDENTS.map(s => ({
  id: s.id,
  name: s.name,
  email: s.email,
  avatar: s.avatar,
}));

// توابع کمکی
export function getStudentById(id: string): Student | undefined {
  return MOCK_STUDENTS.find(s => s.id === id);
}

export function getActiveStudents(): Student[] {
  return MOCK_STUDENTS.filter(s => s.status === 'active');
}

export function searchStudents(query: string): Student[] {
  const lowerQuery = query.toLowerCase();
  return MOCK_STUDENTS.filter(s => 
    s.name.toLowerCase().includes(lowerQuery) ||
    s.email.toLowerCase().includes(lowerQuery)
  );
}
