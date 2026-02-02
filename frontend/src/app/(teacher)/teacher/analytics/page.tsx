"use client";

import { OverviewCards } from '@/components/teacher/analytics/overview-cards';
import { ActivityChart } from '@/components/teacher/analytics/activity-chart';
import { ClassDistribution } from '@/components/teacher/analytics/class-distribution';
import { RecentActivity } from '@/components/teacher/analytics/recent-activity';
import { Button } from '@/components/ui/button';
import { Download, Calendar, ClipboardList, Loader2 } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { StatsSkeleton } from '@/components/dashboard/stats-skeleton';
import { PageTransition } from '@/components/ui/page-transition';
import { ErrorState } from '@/components/shared/error-state';
import { useTeacherAnalytics } from '@/hooks/use-teacher-analytics';
import { useState } from 'react';
import { 
	Dialog, 
	DialogContent, 
	DialogHeader, 
	DialogTitle, 
	DialogTrigger 
} from '@/components/ui/dialog';
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { TeacherService } from '@/services/teacher-service';
import { toast } from 'sonner';

export default function TeacherAnalyticsPage() {
	const { 
		stats, 
		chartData, 
		distributionData, 
		activities, 
		isLoading, 
		error, 
		days, 
		setDays, 
		reload 
	} = useTeacherAnalytics();
	const [isActivityOpen, setIsActivityOpen] = useState(false);
	const [isExporting, setIsExporting] = useState(false);

	const handleExport = async () => {
		try {
			setIsExporting(true);
			const blob = await TeacherService.exportAnalyticsCSV(days);
			const url = window.URL.createObjectURL(blob);
			const a = document.createElement('a');
			a.href = url;
			a.download = `گزارش-تحلیلی-${days}-روزه-${new Date().toLocaleDateString('fa-IR').replace(/\//g, '-')}.csv`;
			document.body.appendChild(a);
			a.click();
			window.URL.revokeObjectURL(url);
			toast.success('گزارش با موفقیت دریافت شد');
		} catch (err) {
			console.error(err);
			toast.error('خطا در دریافت گزارش');
		} finally {
			setIsExporting(false);
		}
	};

	if (isLoading) {
		return (
			<PageTransition>
				<div className="space-y-8">
					<div className="flex justify-between">
						<div className="space-y-2">
							<Skeleton className="h-10 w-64" />
							<Skeleton className="h-4 w-48" />
						</div>
						<div className="flex gap-2">
							<Skeleton className="h-10 w-32" />
							<Skeleton className="h-10 w-32" />
						</div>
					</div>
					<StatsSkeleton />
					<div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
						<Skeleton className="h-[400px] lg:col-span-2 rounded-3xl" />
						<Skeleton className="h-[400px] rounded-3xl" />
					</div>
				</div>
			</PageTransition>
		);
	}

	if (error) {
		return (
			<PageTransition>
				<div className="flex items-center justify-center h-[60vh] px-4">
					<div className="w-full max-w-2xl">
						<ErrorState title="خطا در دریافت اطلاعات تحلیلی" description={error} onRetry={reload} />
					</div>
				</div>
			</PageTransition>
		);
	}

	return (
		<PageTransition>
			<div className="space-y-8">
				<div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
					<div>
						<h1 className="text-2xl md:text-3xl font-black text-foreground">آمار و تحلیل معلم</h1>
						<p className="text-muted-foreground text-sm mt-1">رصد سریع کلاس‌ها و تعامل دانش‌آموزان</p>
					</div>
					<div className="flex flex-col sm:flex-row items-center gap-2">
						<Dialog open={isActivityOpen} onOpenChange={setIsActivityOpen}>
							<DialogTrigger asChild>
								<Button variant="outline" size="sm" className="w-full sm:w-auto h-9 rounded-xl gap-2 border-primary/20 hover:bg-primary/5 text-primary">
									<ClipboardList className="w-4 h-4" />
									گزارش فعالیت‌ها
								</Button>
							</DialogTrigger>
							<DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto rounded-3xl p-0 border-none">
								<DialogHeader className="sr-only">
									<DialogTitle>گزارش فعالیت‌های اخیر</DialogTitle>
								</DialogHeader>
								<RecentActivity activities={activities} isFullWidth />
							</DialogContent>
						</Dialog>

						<DropdownMenu>
							<DropdownMenuTrigger asChild>
								<Button variant="outline" size="sm" className="w-full sm:w-auto h-9 rounded-xl gap-2 hover:bg-muted/50 transition-colors">
									<Calendar className="w-4 h-4 text-primary" />
									{days === 7 ? '۷ روز گذشته' : days === 30 ? '۳۰ روز گذشته' : '۹۰ روز گذشته'}
								</Button>
							</DropdownMenuTrigger>
							<DropdownMenuContent align="end" className="rounded-2xl min-w-[140px]">
								<DropdownMenuItem className="text-right justify-end cursor-pointer" onClick={() => setDays(7)}>۷ روز گذشته</DropdownMenuItem>
								<DropdownMenuItem className="text-right justify-end cursor-pointer" onClick={() => setDays(30)}>۳۰ روز گذشته</DropdownMenuItem>
								<DropdownMenuItem className="text-right justify-end cursor-pointer" onClick={() => setDays(90)}>۹۰ روز گذشته</DropdownMenuItem>
							</DropdownMenuContent>
						</DropdownMenu>

						<Button 
							size="sm" 
							className="w-full sm:w-auto h-9 rounded-xl gap-2 font-bold"
							disabled={isExporting}
							onClick={handleExport}
						>
							{isExporting ? (
								<Loader2 className="w-4 h-4 animate-spin" />
							) : (
								<Download className="w-4 h-4" />
							)}
							خروجی گزارش
						</Button>
					</div>
				</div>

				<OverviewCards stats={stats} />

				<div className="grid grid-cols-1 gap-6">
				<div className="lg:col-span-full">
					<ActivityChart data={chartData} days={days} />
				</div>
				</div>

				<div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
					<ClassDistribution data={distributionData} />
					<div className="lg:col-span-2 bg-muted/30 rounded-3xl border border-dashed border-border flex items-center justify-center p-12">
						<p className="text-muted-foreground text-sm">بخش‌های تحلیلی بیشتر به‌زودی</p>
					</div>
				</div>
			</div>
		</PageTransition>
	);
}

