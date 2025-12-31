'use client';

import { useCallback, useEffect, useState } from 'react';
import { AdminService } from '@/services/admin-service';
import type { ClassDetail, ClassStudent, Course } from '@/types';
import { useMountedRef } from '@/hooks/use-mounted-ref';

type ClassDetailService = {
  getClassDetail: (classId: string) => Promise<ClassDetail>;
  getClassStudents: (classId: string) => Promise<ClassStudent[]>;
  updateClass: (classId: string, data: Partial<Course>) => Promise<{ success: boolean }>;
  deleteClass: (classId: string) => Promise<{ success: boolean }>;
  removeStudentFromClass: (classId: string, studentId: string) => Promise<{ success: boolean }>;
  addStudentToClass: (classId: string, email: string) => Promise<{ success: boolean }>;
};

export function useClassDetail(classId: string, service: ClassDetailService = AdminService) {
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
        service.getClassDetail(classId),
        service.getClassStudents(classId),
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
  }, [classId, mountedRef, service]);

  useEffect(() => {
    reload();
  }, [reload]);

  const updateClass = useCallback(async (data: Partial<Course>) => {
    try {
      setIsUpdating(true);
      const result = await service.updateClass(classId, data);
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
  }, [classId, mountedRef, reload, service]);

  const deleteClass = useCallback(async () => {
    try {
      setIsDeleting(true);
      const result = await service.deleteClass(classId);
      return result;
    } catch (err) {
      console.error(err);
      throw new Error('خطا در حذف کلاس');
    } finally {
      if (mountedRef.current) setIsDeleting(false);
    }
  }, [classId, mountedRef, service]);

  const removeStudent = useCallback(async (studentId: string) => {
    try {
      const result = await service.removeStudentFromClass(classId, studentId);
      if (mountedRef.current && result.success) {
        setStudents(prev => prev.filter(s => s.id !== studentId));
      }
      return result;
    } catch (err) {
      console.error(err);
      throw new Error('خطا در حذف دانش‌آموز');
    }
  }, [classId, mountedRef, service]);

  const addStudent = useCallback(async (email: string) => {
    try {
      const result = await service.addStudentToClass(classId, email);
      if (mountedRef.current && result.success) {
        await reload();
      }
      return result;
    } catch (err) {
      console.error(err);
      throw new Error('خطا در افزودن دانش‌آموز');
    }
  }, [classId, mountedRef, reload, service]);

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
