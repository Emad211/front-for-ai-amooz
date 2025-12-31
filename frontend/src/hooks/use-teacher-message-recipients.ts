import { useMessageRecipients } from './use-message-recipients';
import { TeacherService } from '@/services/teacher-service';

export function useTeacherMessageRecipients() {
  return useMessageRecipients(TeacherService);
}
