'use client';

import { useState } from 'react';
import { UserPlus, Download } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { StudentStats } from '@/components/admin/students/student-stats';
import { StudentFilters } from '@/components/admin/students/student-filters';
import { StudentTable } from '@/components/admin/students/student-table';
import { MOCK_STUDENTS } from '@/constants/mock';

export default function StudentsPage() {
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [performanceFilter, setPerformanceFilter] = useState('all');
  const [sortBy, setSortBy] = useState('recent');

  // Filter and sort students
  const filteredStudents = MOCK_STUDENTS
    .filter(student => {
      const matchesSearch = student.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                           student.email.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesStatus = statusFilter === 'all' || student.status === statusFilter;
      const matchesPerformance = performanceFilter === 'all' || student.performance === performanceFilter;
      return matchesSearch && matchesStatus && matchesPerformance;
    })
    .sort((a, b) => {
      switch (sortBy) {
        case 'recent':
          return new Date(b.lastActivity || 0).getTime() - new Date(a.lastActivity || 0).getTime();
        case 'name':
          return a.name.localeCompare(b.name, 'fa');
        case 'score':
          return b.averageScore - a.averageScore;
        case 'progress':
          return (b.completedLessons / b.totalLessons) - (a.completedLessons / a.totalLessons);
        default:
          return 0;
      }
    });

  // Statistics
  const stats = {
    totalStudents: MOCK_STUDENTS.length,
    activeStudents: MOCK_STUDENTS.filter(s => s.status === 'active').length,
    averageScore: Math.round(MOCK_STUDENTS.reduce((sum, s) => sum + s.averageScore, 0) / MOCK_STUDENTS.length),
    totalEnrollments: MOCK_STUDENTS.reduce((sum, s) => sum + s.enrolledClasses, 0),
  };

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
        searchTerm={searchTerm}
        setSearchTerm={setSearchTerm}
        statusFilter={statusFilter}
        setStatusFilter={setStatusFilter}
        performanceFilter={performanceFilter}
        setPerformanceFilter={setPerformanceFilter}
        sortBy={sortBy}
        setSortBy={setSortBy}
      />

      {/* Students Table */}
      <StudentTable students={filteredStudents} />
    </div>
  );
}