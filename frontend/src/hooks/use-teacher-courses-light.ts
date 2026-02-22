import { useAdminCourses } from './use-admin-courses';
import { TeacherService } from '@/services/teacher-service';
import { useWorkspace } from '@/hooks/use-workspace';

// Lightweight alias for listings without extra filters
export function useTeacherCoursesLight() {
  const { activeWorkspace } = useWorkspace();
  return useAdminCourses(TeacherService, activeWorkspace?.id ?? null);
}
