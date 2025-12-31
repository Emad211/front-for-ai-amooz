import { useStudents } from './use-students';
import { TeacherService } from '@/services/teacher-service';

export function useTeacherStudents() {
  return useStudents(TeacherService);
}
