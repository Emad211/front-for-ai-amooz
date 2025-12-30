'use client';

import { useCallback, useEffect, useState } from 'react';
import { AdminService } from '@/services/admin-service';
import type { ClassDetail, ClassStudent, Course } from '@/types';
import { useMountedRef } from '@/hooks/use-mounted-ref';

export function useClassDetail(classId: string) {
  const mountedRef = useMountedRef();
  const [classDetail, setClassDetail] = useState<ClassDetail | null>(null);
  const [students, setStudents] = useState<ClassStudent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);

  const reload = useCallback(async () => {
    if (!classId) return;
    try {
      setError(null);
      setIsLoading(true);
      const [detail, studentList] = await Promise.all([
        AdminService.getClassDetail(classId),
        AdminService.getClassStudents(classId),
      ]);
      if (mountedRef.current) {
        setClassDetail(detail);
        setStudents(studentList);
      }
    } catch (err) {
      console.error(err);
      if (mountedRef.current) setError('خطا در دریافت اطلاعات کلاس');
    } finally {
      if (mountedRef.current) setIsLoading(false);
    }
  }, [classId, mountedRef]);

  useEffect(() => {
    reload();
  }, [reload]);

  const updateClass = useCallback(async (data: Partial<Course>) => {
    try {
      setIsUpdating(true);
      const result = await AdminService.updateClass(classId, data);
      if (mountedRef.current && result.success) {
        await reload();
      }
      return result;
    } catch (err) {
      console.error(err);
      throw new Error('خطا در بروزرسانی کلاس');
    } finally {
      if (mountedRef.current) setIsUpdating(false);
    }
  }, [classId, mountedRef, reload]);

  const deleteClass = useCallback(async () => {
    try {
      setIsDeleting(true);
      const result = await AdminService.deleteClass(classId);
      return result;
    } catch (err) {
      console.error(err);
      throw new Error('خطا در حذف کلاس');
    } finally {
      if (mountedRef.current) setIsDeleting(false);
    }
  }, [classId, mountedRef]);

  const removeStudent = useCallback(async (studentId: string) => {
    try {
      const result = await AdminService.removeStudentFromClass(classId, studentId);
      if (mountedRef.current && result.success) {
        setStudents(prev => prev.filter(s => s.id !== studentId));
      }
      return result;
    } catch (err) {
      console.error(err);
      throw new Error('خطا در حذف دانش‌آموز');
    }
  }, [classId, mountedRef]);

  const addStudent = useCallback(async (email: string) => {
    try {
      const result = await AdminService.addStudentToClass(classId, email);
      if (mountedRef.current && result.success) {
        await reload();
      }
      return result;
    } catch (err) {
      console.error(err);
      throw new Error('خطا در افزودن دانش‌آموز');
    }
  }, [classId, mountedRef, reload]);

  return {
    classDetail,
    students,
    isLoading,
    error,
    reload,
    updateClass,
    deleteClass,
    removeStudent,
    addStudent,
    isDeleting,
    isUpdating,
  };
}
