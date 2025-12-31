import { useAdminAnalytics } from './use-admin-analytics';
import { TeacherService } from '@/services/teacher-service';

export function useTeacherAnalytics() {
  return useAdminAnalytics(TeacherService);
}
