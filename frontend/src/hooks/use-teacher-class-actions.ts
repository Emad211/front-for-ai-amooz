import { useState } from 'react';
import { TeacherService } from '@/services/teacher-service';

export function useTeacherClassActions(classId: string) {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const updateClass = async (data: any) => {
    try {
      setIsLoading(true);
      setError(null);
      await TeacherService.updateClass(classId, data);
      return true;
    } catch (e) {
      console.error(e);
      setError('خطا در بروزرسانی کلاس');
      return false;
    } finally {
      setIsLoading(false);
    }
  };

  const deleteClass = async () => {
    try {
      setIsLoading(true);
      setError(null);
      await TeacherService.deleteClass(classId);
      return true;
    } catch (e) {
      console.error(e);
      setError('خطا در حذف کلاس');
      return false;
    } finally {
      setIsLoading(false);
    }
  };

  const addStudent = async (email: string) => {
    try {
      setIsLoading(true);
      setError(null);
      await TeacherService.addStudentToClass(classId, email);
      return true;
    } catch (e) {
      console.error(e);
      setError('خطا در افزودن دانش‌آموز');
      return false;
    } finally {
      setIsLoading(false);
    }
  };

  const removeStudent = async (studentId: string) => {
    try {
      setIsLoading(true);
      setError(null);
      await TeacherService.removeStudentFromClass(classId, studentId);
      return true;
    } catch (e) {
      console.error(e);
      setError('خطا در حذف دانش‌آموز');
      return false;
    } finally {
      setIsLoading(false);
    }
  };

  return { updateClass, deleteClass, addStudent, removeStudent, isLoading, error };
}
