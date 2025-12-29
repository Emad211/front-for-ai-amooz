/**
 * =============================================================================
 * USER MOCK DATA - داده‌های آزمایشی کاربر جاری
 * =============================================================================
 * 
 * برای اتصال به Backend:
 * این داده‌ها را با API call به endpoint زیر جایگزین کنید:
 * GET /api/auth/me
 * PUT /api/users/profile
 * 
 * =============================================================================
 */

export interface UserProfile {
  id: string;
  username: string;
  name: string;
  email: string;
  phone: string;
  avatar: string;
  role: 'student' | 'admin' | 'teacher';
  grade?: string;
  major?: string;
  bio?: string;
  location?: string;
  joinDate: string;
  isVerified: boolean;
}

// پروفایل دانش‌آموز
export const MOCK_STUDENT_PROFILE: UserProfile = {
  id: 'user-1',
  username: 'alireza_student',
  name: 'علیرضا رضایی',
  email: 'ali.rezaei@example.com',
  phone: '09123456789',
  avatar: 'https://picsum.photos/seed/user/100/100',
  role: 'student',
  grade: 'دوازدهم',
  major: 'ریاضی فیزیک',
  joinDate: '1402-10-15',
  isVerified: true,
};

// پروفایل ادمین
export const MOCK_ADMIN_USER_PROFILE: UserProfile = {
  id: 'admin-1',
  username: 'admin',
  name: 'مدیر سیستم',
  email: 'admin@ai-amooz.ir',
  phone: '09000000000',
  avatar: 'https://picsum.photos/seed/admin/100/100',
  role: 'admin',
  joinDate: '1401-01-01',
  isVerified: true,
};

// اطلاعات نمایشی کاربر در هدر
export interface UserDisplay {
  name: string;
  email: string;
  avatar?: string;
}

export const MOCK_USER_DISPLAY: UserDisplay = {
  name: MOCK_STUDENT_PROFILE.name,
  email: MOCK_STUDENT_PROFILE.email,
  avatar: MOCK_STUDENT_PROFILE.avatar,
};

// توابع کمکی
export function getCurrentUser(): UserProfile {
  // در آینده از context یا session استفاده می‌شود
  return MOCK_STUDENT_PROFILE;
}

export function isAdmin(user: UserProfile): boolean {
  return user.role === 'admin';
}
