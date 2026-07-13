'use client';

import React, { useState } from 'react';
import { toast } from 'sonner';
import { Download, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { StudentStats } from '@/components/teacher/students/student-stats';
import { StudentFilters } from '@/components/teacher/students/student-filters';
import { StudentTable } from '@/components/teacher/students/student-table';
import { Skeleton } from '@/components/ui/skeleton';
import { ErrorState } from '@/components/shared/error-state';
import { useTeacherStudents } from '@/hooks/use-teacher-students';
import { formatPersianDate } from '@/lib/date-utils';
import { AddStudentsDialog } from '@/components/teacher/students/add-students-dialog';
import { PendingInvitations } from '@/components/teacher/students/pending-invitations';

export default function TeacherStudentsPage() {
	const { students, stats, isLoading, error, reload, filters } = useTeacherStudents();
	const [exporting, setExporting] = useState(false);
	const [refreshKey, setRefreshKey] = useState(0);

	const handleExport = async () => {
		if (!students.length) {
			toast.error('دانش‌آموزی برای خروجی گرفتن وجود ندارد');
			return;
		}
		setExporting(true);
		try {
			const ExcelJS = await import('exceljs');
			const workbook = new ExcelJS.Workbook();
			const sheet = workbook.addWorksheet('دانش‌آموزان', { views: [{ rightToLeft: true, state: 'frozen', ySplit: 1 }] });
			sheet.columns = [
				{ header: 'نام', key: 'name', width: 24 }, { header: 'ایمیل', key: 'email', width: 30 },
				{ header: 'تلفن', key: 'phone', width: 16 }, { header: 'کلاس‌ها', key: 'classes', width: 12 },
				{ header: 'دروس تکمیل‌شده', key: 'completed', width: 18 }, { header: 'کل دروس', key: 'total', width: 12 },
				{ header: 'میانگین نمره', key: 'score', width: 16 }, { header: 'وضعیت', key: 'status', width: 14 },
				{ header: 'تاریخ عضویت', key: 'joined', width: 18 },
			];
			students.forEach((student) => sheet.addRow({ name: student.name, email: student.email, phone: student.phone, classes: student.enrolledClasses, completed: student.completedLessons, total: student.totalLessons, score: student.averageScore, status: student.status === 'active' ? 'فعال' : student.status === 'suspended' ? 'تعلیق‌شده' : 'غیرفعال', joined: formatPersianDate(student.joinDate) }));
			sheet.getRow(1).font = { bold: true };
			sheet.autoFilter = { from: 'A1', to: 'I1' };
			const buffer = await workbook.xlsx.writeBuffer();
			const blob = new Blob([buffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
			const url = URL.createObjectURL(blob);
			const link = document.createElement('a'); link.href = url; link.download = `students-${new Date().toISOString().slice(0, 10)}.xlsx`; link.click(); URL.revokeObjectURL(url);
			toast.success('فایل اکسل آماده شد.');
		} catch { toast.error('ساخت فایل اکسل انجام نشد.'); } finally { setExporting(false); }
	};

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
			<div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
				<div className="text-start">
					<h1 className="text-2xl md:text-3xl font-black text-foreground">دانش‌آموزان</h1>
					<p className="text-muted-foreground text-sm mt-1">
						مدیریت و پیگیری دانش‌آموزان
					</p>
				</div>
				<div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
					<Button variant="outline" size="sm" onClick={handleExport} disabled={exporting} className="w-full sm:w-auto h-10 rounded-xl gap-2">
						{exporting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
						خروجی Excel
					</Button>
					<AddStudentsDialog onCompleted={() => setRefreshKey((value) => value + 1)} />
				</div>
			</div>

			<StudentStats stats={stats} />

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

			<StudentTable students={students} onChanged={reload} />
			<PendingInvitations refreshKey={refreshKey} />
		</div>
	);
}

