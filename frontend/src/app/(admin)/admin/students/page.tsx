'use client';

import { useState } from 'react';
import { UserPlus, Download } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { StudentStats } from '@/components/admin/students/student-stats';
import { StudentFilters } from '@/components/admin/students/student-filters';
import { StudentTable } from '@/components/admin/students/student-table';

// Mock data for students
const mockStudents = [
  {
    id: '1',
    name: 'علی احمدی',
    email: 'ali.ahmadi@example.com',
    phone: '09121234567',
    avatar: '/api/placeholder/100/100',
    enrolledClasses: 3,
    completedLessons: 24,
    totalLessons: 45,
    averageScore: 85,
    status: 'active',
    joinDate: '2024-01-10',
    lastActivity: '2024-01-22',
    performance: 'excellent',
  },
  {
    id: '2',
    name: 'زهرا محمدی',
    email: 'zahra.mohammadi@example.com',
    phone: '09129876543',
    avatar: '/api/placeholder/100/100',
    enrolledClasses: 5,
    completedLessons: 67,
    totalLessons: 90,
    averageScore: 92,
    status: 'active',
    joinDate: '2023-12-15',
    lastActivity: '2024-01-23',
    performance: 'excellent',
  },
  {
    id: '3',
    name: 'محمد رضایی',
    email: 'mohammad.rezaei@example.com',
    phone: '09135551234',
    avatar: '/api/placeholder/100/100',
    enrolledClasses: 2,
    completedLessons: 15,
    totalLessons: 30,
    averageScore: 72,
    status: 'active',
    joinDate: '2024-01-18',
    lastActivity: '2024-01-21',
    performance: 'good',
  },
  {
    id: '4',
    name: 'فاطمه کریمی',
    email: 'fatemeh.karimi@example.com',
    phone: '09141239876',
    avatar: '/api/placeholder/100/100',
    enrolledClasses: 4,
    completedLessons: 38,
    totalLessons: 60,
    averageScore: 78,
    status: 'active',
    joinDate: '2024-01-05',
    lastActivity: '2024-01-20',
    performance: 'good',
  },
  {
    id: '5',
    name: 'حسین نوری',
    email: 'hossein.noori@example.com',
    phone: '09151234567',
    avatar: '/api/placeholder/100/100',
    enrolledClasses: 2,
    completedLessons: 8,
    totalLessons: 30,
    averageScore: 58,
    status: 'inactive',
    joinDate: '2023-12-20',
    lastActivity: '2024-01-10',
    performance: 'needs-improvement',
  },
  {
    id: '6',
    name: 'مریم صادقی',
    email: 'maryam.sadeghi@example.com',
    phone: '09161234567',
    avatar: '/api/placeholder/100/100',
    enrolledClasses: 6,
    completedLessons: 89,
    totalLessons: 100,
    averageScore: 95,
    status: 'active',
    joinDate: '2023-11-10',
    lastActivity: '2024-01-23',
    performance: 'excellent',
  },
];

export default function StudentsPage() {
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [performanceFilter, setPerformanceFilter] = useState('all');
  const [sortBy, setSortBy] = useState('recent');

  // Filter and sort students
  const filteredStudents = mockStudents
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
          return new Date(b.lastActivity).getTime() - new Date(a.lastActivity).getTime();
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
    totalStudents: mockStudents.length,
    activeStudents: mockStudents.filter(s => s.status === 'active').length,
    averageScore: Math.round(mockStudents.reduce((sum, s) => sum + s.averageScore, 0) / mockStudents.length),
    totalEnrollments: mockStudents.reduce((sum, s) => sum + s.enrolledClasses, 0),
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-foreground">دانش‌آموزان</h1>
          <p className="text-muted-foreground mt-1">
            مدیریت و پیگیری دانش‌آموزان
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline">
            <Download className="w-4 h-4 ml-2" />
            خروجی Excel
          </Button>
          <Button>
            <UserPlus className="w-4 h-4 ml-2" />
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