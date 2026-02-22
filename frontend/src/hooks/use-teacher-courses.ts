import { useAdminCourses } from './use-admin-courses';
import { TeacherService } from '@/services/teacher-service';
import { useWorkspace } from '@/hooks/use-workspace';

export function useTeacherCourses() {
  const { activeWorkspace } = useWorkspace();
  return useAdminCourses(TeacherService, activeWorkspace?.id ?? null);
}
