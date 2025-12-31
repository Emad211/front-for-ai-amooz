import { useAdminCourses } from './use-admin-courses';
import { TeacherService } from '@/services/teacher-service';

// Lightweight alias for listings without extra filters
export function useTeacherCoursesLight() {
  return useAdminCourses(TeacherService);
}
