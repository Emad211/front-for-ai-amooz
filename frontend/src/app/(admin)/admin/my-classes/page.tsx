'use client';

import { useState } from 'react';
import { Plus, BookOpen } from 'lucide-react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { ClassStats } from '@/components/admin/my-classes/class-stats';
import { ClassFilters } from '@/components/admin/my-classes/class-filters';
import { ClassCard } from '@/components/admin/my-classes/class-card';
import { MOCK_COURSES } from '@/constants/mock';

export default function MyClassesPage() {
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [categoryFilter, setCategoryFilter] = useState('all');
  const [sortBy, setSortBy] = useState('recent');

  // Get unique categories
  const categories = Array.from(new Set(MOCK_COURSES.map(cls => cls.category)));

  // Filter and sort classes
  const filteredClasses = MOCK_COURSES
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
          return new Date(b.lastActivity || 0).getTime() - new Date(a.lastActivity || 0).getTime();
        case 'oldest':
          return new Date(a.createdAt || 0).getTime() - new Date(b.createdAt || 0).getTime();
        case 'students':
          return (b.studentsCount || 0) - (a.studentsCount || 0);
        case 'progress':
          return (b.progress || 0) - (a.progress || 0);
        case 'rating':
          return (b.rating || 0) - (a.rating || 0);
        default:
          return 0;
      }
    });

  // Statistics
  const stats = {
    totalClasses: MOCK_COURSES.length,
    activeClasses: MOCK_COURSES.filter(cls => cls.status === 'active').length,
    totalStudents: MOCK_COURSES.reduce((sum, cls) => sum + (cls.studentsCount || 0), 0),
    averageRating: (MOCK_COURSES.reduce((sum, cls) => sum + (cls.rating || 0), 0) / MOCK_COURSES.length).toFixed(1),
  };

  return (
    <div className="space-y-8">
      {/* Header Section */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl md:text-3xl font-black text-foreground">کلاس‌های من</h1>
          <p className="text-muted-foreground text-sm mt-1">
            مدیریت و پیگیری کلاس‌های آموزشی شما
          </p>
        </div>
        <Button asChild size="sm" className="w-full md:w-auto h-9 rounded-xl">
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