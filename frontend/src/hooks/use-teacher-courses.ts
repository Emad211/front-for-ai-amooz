import { useAdminCourses } from './use-admin-courses';
import { TeacherService } from '@/services/teacher-service';

export function useTeacherCourses() {
  return useAdminCourses(TeacherService);
}
