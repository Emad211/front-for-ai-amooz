'use client';

import { useState } from 'react';
import { Plus, FileQuestion, CheckCircle, Clock, FileEdit, Search, MoreVertical, Eye, Trash2, Calendar, Users } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { ErrorState } from '@/components/shared/error-state';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { useTeacherExamPreps } from '@/hooks/use-teacher-exam-preps';
import { ExamPrepSessionDetail, deleteExamPrepSession } from '@/services/classes-service';
import { formatDistanceToNow } from 'date-fns';
import { faIR } from 'date-fns/locale';
import { toast } from 'sonner';

function ExamPrepStats({ stats }: { stats: { total: number; published: number; processing: number; draft: number } }) {
  const statItems = [
    { label: 'کل آزمون‌ها', value: stats.total, icon: FileQuestion, color: 'text-primary' },
    { label: 'منتشر شده', value: stats.published, icon: CheckCircle, color: 'text-emerald-500' },
    { label: 'در حال پردازش', value: stats.processing, icon: Clock, color: 'text-amber-500' },
    { label: 'پیش‌نویس', value: stats.draft, icon: FileEdit, color: 'text-muted-foreground' },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {statItems.map((item) => (
        <Card key={item.label} className="rounded-xl border-border/50">
          <CardContent className="p-4 flex items-center gap-3">
            <div className={`p-2 rounded-lg bg-background ${item.color}`}>
              <item.icon className="w-5 h-5" />
            </div>
            <div>
              <p className="text-2xl font-black">{item.value}</p>
              <p className="text-xs text-muted-foreground">{item.label}</p>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function ExamPrepFilters({
  searchTerm,
  setSearchTerm,
  statusFilter,
  setStatusFilter,
  sortBy,
  setSortBy,
}: {
  searchTerm: string;
  setSearchTerm: (term: string) => void;
  statusFilter: string;
  setStatusFilter: (status: string) => void;
  sortBy: string;
  setSortBy: (sort: string) => void;
}) {
  return (
    <div className="flex flex-col md:flex-row gap-3">
      <div className="relative flex-1">
        <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <Input
          type="text"
          placeholder="جستجو در آزمون‌ها..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="pr-10 rounded-xl h-10"
        />
      </div>
      <Select value={statusFilter} onValueChange={setStatusFilter}>
        <SelectTrigger className="w-full md:w-40 rounded-xl h-10">
          <SelectValue placeholder="وضعیت" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">همه</SelectItem>
          <SelectItem value="published">منتشر شده</SelectItem>
          <SelectItem value="processing">در حال پردازش</SelectItem>
          <SelectItem value="draft">پیش‌نویس</SelectItem>
        </SelectContent>
      </Select>
      <Select value={sortBy} onValueChange={setSortBy}>
        <SelectTrigger className="w-full md:w-40 rounded-xl h-10">
          <SelectValue placeholder="مرتب‌سازی" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="recent">جدیدترین</SelectItem>
          <SelectItem value="oldest">قدیمی‌ترین</SelectItem>
          <SelectItem value="title">عنوان</SelectItem>
        </SelectContent>
      </Select>
    </div>
  );
}

const statusConfig: Record<string, { label: string; color: string }> = {
  published: { label: 'منتشر شده', color: 'bg-primary/10 text-primary border-primary/20' },
  processing: { label: 'در حال پردازش', color: 'bg-amber-500/10 text-amber-600 border-amber-500/20' },
  draft: { label: 'پیش‌نویس', color: 'bg-muted text-muted-foreground border-border' },
  failed: { label: 'خطا', color: 'bg-destructive/10 text-destructive border-destructive/20' },
};

function ExamPrepCard({ examPrep, onDeleted }: { examPrep: ExamPrepSessionDetail; onDeleted: () => void }) {
  const router = useRouter();
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const getStatus = () => {
    if (examPrep.is_published) return 'published';
    if (['exam_transcribing', 'exam_structuring'].includes(examPrep.status)) return 'processing';
    if (examPrep.status === 'failed') return 'failed';
    return 'draft';
  };

  const currentStatus = getStatus();
  const questionCount = examPrep.exam_prep_data?.exam_prep?.questions?.length ?? 0;

  const handleDelete = async () => {
    try {
      setIsDeleting(true);
      await deleteExamPrepSession(examPrep.id);
      toast.success('آزمون با موفقیت حذف شد');
      setIsDeleteDialogOpen(false);
      onDeleted();
    } catch {
      toast.error('خطا در حذف آزمون');
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <>
      <Card className="group hover:shadow-md transition-all duration-300 border-border/60 bg-card hover:border-primary/50 overflow-hidden relative">
        <div className="absolute top-0 right-0 w-1 h-full bg-primary/0 group-hover:bg-primary transition-all duration-300" />

        <CardHeader className="pb-3 pt-5 px-5">
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-1.5 flex-1">
              <div className="flex items-center gap-2 mb-1">
                <Badge variant="outline" className={`rounded-md px-2 py-0.5 text-[10px] font-normal border ${statusConfig[currentStatus]?.color || ''}`}>
                  {statusConfig[currentStatus]?.label || currentStatus}
                </Badge>
                {examPrep.level && (
                  <Badge variant="outline" className="rounded-md px-2 py-0.5 text-[10px] font-normal border bg-muted text-muted-foreground border-border">
                    {examPrep.level}
                  </Badge>
                )}
              </div>
              <CardTitle className="text-lg font-bold text-foreground group-hover:text-primary transition-colors line-clamp-1">
                {examPrep.title}
              </CardTitle>
              <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed h-9">
                {examPrep.description || 'بدون توضیحات'}
              </p>
            </div>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" className="h-8 w-8 -ml-2 text-muted-foreground hover:text-foreground">
                  <MoreVertical className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-48">
                <DropdownMenuItem asChild>
                  <Link href={`/teacher/my-exams/${examPrep.id}`}>
                    <Eye className="w-4 h-4 ml-2" />
                    مشاهده جزئیات
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  className="text-destructive focus:text-destructive"
                  onClick={() => setIsDeleteDialogOpen(true)}
                >
                  <Trash2 className="w-4 h-4 ml-2" />
                  حذف آزمون
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </CardHeader>

        <CardContent className="px-5 pb-5">
          <div className="grid grid-cols-2 gap-3 mb-4">
            <div className="flex items-center gap-2 bg-muted/50 p-2 rounded-lg">
              <div className="h-8 w-8 rounded-full bg-background flex items-center justify-center text-muted-foreground shrink-0">
                <FileQuestion className="h-4 w-4" />
              </div>
              <div className="flex flex-col min-w-0">
                <span className="text-[10px] text-muted-foreground leading-none mb-0.5">تعداد سوالات</span>
                <span className="text-xs font-bold truncate">{questionCount}</span>
              </div>
            </div>
            <div className="flex items-center gap-2 bg-muted/50 p-2 rounded-lg">
              <div className="h-8 w-8 rounded-full bg-background flex items-center justify-center text-muted-foreground shrink-0">
                <Users className="h-4 w-4" />
              </div>
              <div className="flex flex-col min-w-0">
                <span className="text-[10px] text-muted-foreground leading-none mb-0.5">دانش‌آموزان</span>
                <span className="text-xs font-bold truncate">—</span>
              </div>
            </div>
          </div>

          <div className="flex items-center justify-between text-xs text-muted-foreground border-t border-border/50 pt-3 mt-2">
            <div className="flex items-center gap-1">
              <Calendar className="h-3 w-3" />
              <span>
                {formatDistanceToNow(new Date(examPrep.created_at), { addSuffix: true, locale: faIR })}
              </span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>حذف آزمون</AlertDialogTitle>
            <AlertDialogDescription>
              آیا از حذف آزمون «{examPrep.title}» مطمئن هستید؟ این عملیات قابل بازگشت نیست.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>انصراف</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              disabled={isDeleting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isDeleting ? 'در حال حذف...' : 'حذف آزمون'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

export default function TeacherMyExamsPage() {
  const { examPreps, stats, isLoading, error, reload, filters } = useTeacherExamPreps();
  const [sortBy, setSortBy] = useState('recent');

  const sortedExamPreps = [...examPreps].sort((a, b) => {
    switch (sortBy) {
      case 'recent':
        return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
      case 'oldest':
        return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      case 'title':
        return a.title.localeCompare(b.title, 'fa');
      default:
        return 0;
    }
  });

  if (error) {
    return (
      <div className="flex items-center justify-center h-[60vh] px-4">
        <div className="w-full max-w-2xl">
          <ErrorState title="خطا در دریافت آزمون‌ها" description={error} onRetry={reload} />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl md:text-3xl font-black text-foreground">آزمون‌های من</h1>
          <p className="text-muted-foreground text-sm mt-1">مدیریت و پیگیری آزمون‌های آمادگی شما</p>
        </div>
        <Button asChild size="sm" className="w-full md:w-auto h-9 rounded-xl">
          <Link href="/teacher/create-class?type=exam-prep">
            <Plus className="w-4 h-4 ml-2" />
            ایجاد آزمون جدید
          </Link>
        </Button>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Skeleton className="h-24 rounded-xl" />
          <Skeleton className="h-24 rounded-xl" />
          <Skeleton className="h-24 rounded-xl" />
          <Skeleton className="h-24 rounded-xl" />
        </div>
      ) : (
        <ExamPrepStats stats={stats} />
      )}

      <ExamPrepFilters
        searchTerm={filters.searchTerm}
        setSearchTerm={filters.setSearchTerm}
        statusFilter={filters.statusFilter}
        setStatusFilter={filters.setStatusFilter}
        sortBy={sortBy}
        setSortBy={setSortBy}
      />

      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            {isLoading ? 'در حال بارگذاری...' : `${sortedExamPreps.length} آزمون یافت شد`}
          </p>
        </div>

        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
            <Skeleton className="h-48 rounded-2xl" />
            <Skeleton className="h-48 rounded-2xl" />
            <Skeleton className="h-48 rounded-2xl" />
          </div>
        ) : sortedExamPreps.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
            {sortedExamPreps.map((ep) => (
              <ExamPrepCard key={ep.id} examPrep={ep} onDeleted={reload} />
            ))}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center py-12 border-2 border-dashed border-border/50 rounded-3xl bg-muted/10">
            <div className="p-4 bg-background rounded-full shadow-xl mb-4">
              <FileQuestion className="h-8 w-8 text-primary/40" />
            </div>
            <p className="text-muted-foreground font-bold">آزمونی یافت نشد</p>
            <p className="text-sm text-muted-foreground mt-1">اولین آزمون خود را بسازید</p>
          </div>
        )}
      </div>
    </div>
  );
}
