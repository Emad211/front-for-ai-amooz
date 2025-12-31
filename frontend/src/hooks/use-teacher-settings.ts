import { useAdminSettings } from './use-admin-settings';
import { TeacherService } from '@/services/teacher-service';

export function useTeacherSettings() {
  return useAdminSettings(TeacherService);
}
