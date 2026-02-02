'use client';

import { useState } from 'react';
import { Plus, BookOpen } from 'lucide-react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { ClassStats } from '@/components/teacher/my-classes/class-stats';
import { ClassFilters } from '@/components/teacher/my-classes/class-filters';
import { ClassCard } from '@/components/teacher/my-classes/class-card';
import { Skeleton } from '@/components/ui/skeleton';
import { ErrorState } from '@/components/shared/error-state';
import { useTeacherCourses } from '@/hooks/use-teacher-courses';

export default function TeacherMyClassesPage() {
	const { courses, categories, stats, isLoading, error, reload, filters } = useTeacherCourses();
	const [sortBy, setSortBy] = useState('recent');

	const sortedClasses = [...courses].sort((a, b) => {
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

	if (error) {
		return (
			<div className="flex items-center justify-center h-[60vh] px-4">
				<div className="w-full max-w-2xl">
					<ErrorState title="خطا در دریافت کلاس‌ها" description={error} onRetry={reload} />
				</div>
			</div>
		);
	}

	return (
		<div className="space-y-8">
			<div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
				<div>
					<h1 className="text-2xl md:text-3xl font-black text-foreground">کلاس‌های من</h1>
					<p className="text-muted-foreground text-sm mt-1">مدیریت و پیگیری کلاس‌های آموزشی شما</p>
				</div>
				<Button asChild size="sm" className="w-full md:w-auto h-9 rounded-xl">
					<Link href="/teacher/create-class">
						<Plus className="w-4 h-4 ml-2" />
						ایجاد کلاس جدید
					</Link>
				</Button>
			</div>

			{isLoading ? (
				<div className="grid grid-cols-1 md:grid-cols-4 gap-4">
					<Skeleton className="h-24 rounded-xl" />
					<Skeleton className="h-24 rounded-xl" />
					<Skeleton className="h-24 rounded-xl" />
					<Skeleton className="h-24 rounded-xl" />
				</div>
			) : (
				<ClassStats stats={stats} />
			)}

			<ClassFilters 
				searchTerm={filters.searchTerm}
				setSearchTerm={filters.setSearchTerm}
				statusFilter={filters.categoryFilter}
				setStatusFilter={filters.setCategoryFilter}
				categoryFilter={filters.categoryFilter}
				setCategoryFilter={filters.setCategoryFilter}
				sortBy={sortBy}
				setSortBy={setSortBy}
				categories={categories}
			/>

			<div className="space-y-4">
				<div className="flex items-center justify-between">
					<p className="text-sm text-muted-foreground">
						{isLoading ? 'در حال بارگذاری...' : `${sortedClasses.length} کلاس یافت شد`}
					</p>
				</div>

				{isLoading ? (
					<div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
						<Skeleton className="h-64 rounded-2xl" />
						<Skeleton className="h-64 rounded-2xl" />
						<Skeleton className="h-64 rounded-2xl" />
					</div>
				) : sortedClasses.length > 0 ? (
					<div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
						{sortedClasses.map((cls) => (
							<ClassCard key={cls.id} cls={cls as any} basePath="/teacher" onDelete={reload} />
						))}
					</div>
				) : (
					<div className="flex flex-col items-center justify-center py-12 border-2 border-dashed border-border/50 rounded-3xl bg-muted/10">
						<div className="p-4 bg-background rounded-full shadow-xl mb-4">
							<BookOpen className="h-8 w-8 text-primary/40" />
						</div>
						<p className="text-muted-foreground font-bold">کلاسی یافت نشد</p>
					</div>
				)}
			</div>
		</div>
	);
}

