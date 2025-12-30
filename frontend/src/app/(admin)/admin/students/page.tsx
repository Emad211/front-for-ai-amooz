'use client';

import React from 'react';
import { UserPlus, Download } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { StudentStats } from '@/components/admin/students/student-stats';
import { StudentFilters } from '@/components/admin/students/student-filters';
import { StudentTable } from '@/components/admin/students/student-table';
import { useStudents } from '@/hooks/use-students';
import { Skeleton } from '@/components/ui/skeleton';
import { ErrorState } from '@/components/shared/error-state';

export default function StudentsPage() {
  const { students, stats, isLoading, error, reload, filters } = useStudents();

  if (isLoading) {
    return (
      <div className="space-y-8">
        <div className="flex justify-between">
          <Skeleton className="h-10 w-48" />
          <div className="flex gap-2">
            <Skeleton className="h-10 w-32" />
            <Skeleton className="h-10 w-32" />
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Skeleton className="h-24 rounded-xl" />
          <Skeleton className="h-24 rounded-xl" />
          <Skeleton className="h-24 rounded-xl" />
          <Skeleton className="h-24 rounded-xl" />
        </div>
        <Skeleton className="h-[500px] w-full rounded-2xl" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-[60vh] px-4">
        <div className="w-full max-w-2xl">
          <ErrorState title="خطا در دریافت دانش‌آموزان" description={error} onRetry={reload} />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="text-start">
          <h1 className="text-2xl md:text-3xl font-black text-foreground">دانش‌آموزان</h1>
          <p className="text-muted-foreground text-sm mt-1">
            مدیریت و پیگیری دانش‌آموزان
          </p>
        </div>
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
          <Button variant="outline" size="sm" className="w-full sm:w-auto h-10 rounded-xl gap-2">
            <Download className="w-4 h-4" />
            خروجی Excel
          </Button>
          <Button size="sm" className="w-full sm:w-auto h-10 rounded-xl gap-2">
            <UserPlus className="w-4 h-4" />
            افزودن دانش‌آموز
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <StudentStats stats={stats} />

      {/* Filters and Search */}
      <StudentFilters 
        searchTerm={filters.searchTerm}
        setSearchTerm={filters.setSearchTerm}
        statusFilter={filters.statusFilter}
        setStatusFilter={filters.setStatusFilter}
        performanceFilter={filters.performanceFilter}
        setPerformanceFilter={filters.setPerformanceFilter}
        sortBy={filters.sortBy}
        setSortBy={filters.setSortBy}
      />

      {/* Students Table */}
      <StudentTable students={students} />
    </div>
  );
}