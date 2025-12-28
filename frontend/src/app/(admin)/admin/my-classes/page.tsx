'use client';

import { useState } from 'react';
import { Plus, BookOpen } from 'lucide-react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { ClassStats } from '@/components/admin/my-classes/class-stats';
import { ClassFilters } from '@/components/admin/my-classes/class-filters';
import { ClassCard } from '@/components/admin/my-classes/class-card';

// Mock data for classes
const mockClasses = [
  {
    id: '1',
    title: 'ریاضی پیشرفته',
    description: 'کلاس ریاضی برای دانش‌آموزان سال سوم دبیرستان',
    studentsCount: 24,
    lessonsCount: 12,
    status: 'active',
    createdAt: '2024-01-15',
    lastActivity: '2024-01-20',
    category: 'ریاضی',
    level: 'پیشرفته',
    thumbnail: '/api/placeholder/300/200',
    rating: 4.8,
    reviews: 15,
  },
  {
    id: '2',
    title: 'فیزیک کنکور',
    description: 'آماده‌سازی برای کنکور فیزیک با تست‌های متنوع',
    studentsCount: 45,
    lessonsCount: 20,
    status: 'active',
    createdAt: '2024-01-10',
    lastActivity: '2024-01-22',
    category: 'فیزیک',
    level: 'متوسط',
    thumbnail: '/api/placeholder/300/200',
    rating: 4.9,
    reviews: 28,
  },
  {
    id: '3',
    title: 'شیمی آلی',
    description: 'اصول و مبانی شیمی آلی برای دانشجویان',
    studentsCount: 18,
    lessonsCount: 8,
    status: 'draft',
    createdAt: '2024-01-18',
    lastActivity: '2024-01-19',
    category: 'شیمی',
    level: 'مبتدی',
    thumbnail: '/api/placeholder/300/200',
    rating: 4.5,
    reviews: 8,
  },
  {
    id: '4',
    title: 'زبان انگلیسی محاورات',
    description: 'تقویت مهارت‌های مکالمه انگلیسی',
    studentsCount: 32,
    lessonsCount: 15,
    status: 'active',
    createdAt: '2024-01-05',
    lastActivity: '2024-01-21',
    category: 'زبان',
    level: 'متوسط',
    thumbnail: '/api/placeholder/300/200',
    rating: 4.7,
    reviews: 22,
  },
  {
    id: '5',
    title: 'برنامه‌نویسی پایتون',
    description: 'آموزش کامل برنامه‌نویسی پایتون از صفر',
    studentsCount: 67,
    lessonsCount: 25,
    status: 'paused',
    createdAt: '2023-12-20',
    lastActivity: '2024-01-15',
    category: 'برنامه‌نویسی',
    level: 'مبتدی',
    thumbnail: '/api/placeholder/300/200',
    rating: 4.6,
    reviews: 41,
  },
];

export default function MyClassesPage() {
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [categoryFilter, setCategoryFilter] = useState('all');
  const [sortBy, setSortBy] = useState('recent');

  // Get unique categories
  const categories = Array.from(new Set(mockClasses.map(cls => cls.category)));

  // Filter and sort classes
  const filteredClasses = mockClasses
    .filter(cls => {
      const matchesSearch = cls.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
                           cls.description.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesStatus = statusFilter === 'all' || cls.status === statusFilter;
      const matchesCategory = categoryFilter === 'all' || cls.category === categoryFilter;
      return matchesSearch && matchesStatus && matchesCategory;
    })
    .sort((a, b) => {
      switch (sortBy) {
        case 'recent':
          return new Date(b.lastActivity).getTime() - new Date(a.lastActivity).getTime();
        case 'oldest':
          return new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime();
        case 'students':
          return b.studentsCount - a.studentsCount;
        case 'progress':
          return b.progress - a.progress;
        case 'rating':
          return b.rating - a.rating;
        default:
          return 0;
      }
    });

  // Statistics
  const stats = {
    totalClasses: mockClasses.length,
    activeClasses: mockClasses.filter(cls => cls.status === 'active').length,
    totalStudents: mockClasses.reduce((sum, cls) => sum + cls.studentsCount, 0),
    averageRating: (mockClasses.reduce((sum, cls) => sum + cls.rating, 0) / mockClasses.length).toFixed(1),
  };

  return (
    <div className="space-y-8">
      {/* Header Section */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-foreground">کلاس‌های من</h1>
          <p className="text-muted-foreground mt-1">
            مدیریت و پیگیری کلاس‌های آموزشی شما
          </p>
        </div>
        <Button asChild className="w-fit">
          <Link href="/admin/create-class">
            <Plus className="w-4 h-4 ml-2" />
            ایجاد کلاس جدید
          </Link>
        </Button>
      </div>

      {/* Stats Cards */}
      <ClassStats stats={stats} />

      {/* Filters and Search */}
      <ClassFilters 
        searchTerm={searchTerm}
        setSearchTerm={setSearchTerm}
        statusFilter={statusFilter}
        setStatusFilter={setStatusFilter}
        categoryFilter={categoryFilter}
        setCategoryFilter={setCategoryFilter}
        sortBy={sortBy}
        setSortBy={setSortBy}
        categories={categories}
      />

      {/* Results */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            {filteredClasses.length} کلاس یافت شد
          </p>
        </div>

        {/* Classes Grid */}
        {filteredClasses.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
            {filteredClasses.map((cls) => (
              <ClassCard key={cls.id} cls={cls} />
            ))}
          </div>
        ) : (
          <Card className="border-dashed border-2 border-muted-foreground/25">
            <CardContent className="flex flex-col items-center justify-center py-12">
              <BookOpen className="w-12 h-12 text-muted-foreground/50 mb-4" />
              <h3 className="text-lg font-semibold text-muted-foreground mb-2">
                هیچ کلاسی یافت نشد
              </h3>
              <p className="text-muted-foreground text-center max-w-sm">
                بر اساس فیلترهای اعمال شده، کلاسی پیدا نشد. فیلترها را تغییر دهید یا کلاس جدید ایجاد کنید.
              </p>
              <Button asChild className="mt-4">
                <Link href="/admin/create-class">
                  <Plus className="w-4 h-4 ml-2" />
                  ایجاد کلاس جدید
                </Link>
              </Button>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}