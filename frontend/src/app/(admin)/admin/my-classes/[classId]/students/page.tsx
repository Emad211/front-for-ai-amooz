'use client';

import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useState } from 'react';
import { 
  ArrowRight, 
  Search, 
  UserPlus, 
  MoreVertical,
  Mail,
  Trash2,
  Download,
  Filter,
  SortAsc,
  UserX
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Skeleton } from '@/components/ui/skeleton';
import { ErrorState } from '@/components/shared/error-state';
import { useClassDetail } from '@/hooks/use-class-detail';
import { Progress } from '@/components/ui/progress';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { toast } from 'sonner';

const statusConfig = {
  active: { label: 'فعال', color: 'bg-emerald-500/10 text-emerald-600' },
  inactive: { label: 'غیرفعال', color: 'bg-slate-500/10 text-slate-600' },
};

const performanceConfig = {
  excellent: { label: 'عالی', color: 'text-emerald-600' },
  good: { label: 'خوب', color: 'text-blue-600' },
  'needs-improvement': { label: 'نیاز به تلاش', color: 'text-amber-600' },
};

export default function ClassStudentsPage() {
  const params = useParams();
  const router = useRouter();
  const classId = Array.isArray(params?.classId) ? params.classId[0] : params?.classId || '';
  
  const { classDetail, students, isLoading, error, reload, removeStudent, addStudent } = useClassDetail(classId);
  
  const [searchTerm, setSearchTerm] = useState('');
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [newStudentEmail, setNewStudentEmail] = useState('');
  const [isAdding, setIsAdding] = useState(false);

  const filteredStudents = students.filter(student => 
    student.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    student.email.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const handleRemoveStudent = async (studentId: string, studentName: string) => {
    try {
      await removeStudent(studentId);
      toast.success(`${studentName} از کلاس حذف شد`);
    } catch {
      toast.error('خطا در حذف دانش‌آموز');
    }
  };

  const handleAddStudent = async () => {
    if (!newStudentEmail.trim()) {
      toast.error('لطفاً ایمیل دانش‌آموز را وارد کنید');
      return;
    }
    try {
      setIsAdding(true);
      await addStudent(newStudentEmail);
      toast.success('دانش‌آموز با موفقیت اضافه شد');
      setNewStudentEmail('');
      setIsAddDialogOpen(false);
    } catch {
      toast.error('خطا در افزودن دانش‌آموز');
    } finally {
      setIsAdding(false);
    }
  };

  if (error) {
    return (
      <div className="flex items-center justify-center h-[60vh] px-4">
        <div className="w-full max-w-2xl">
          <ErrorState title="خطا در دریافت اطلاعات" description={error} onRetry={reload} />
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-48" />
        <Skeleton className="h-16 rounded-xl" />
        <Skeleton className="h-96 rounded-xl" />
      </div>
    );
  }

  if (!classDetail) {
    return (
      <div className="flex items-center justify-center h-[60vh] px-4">
        <div className="w-full max-w-2xl">
          <ErrorState title="کلاس یافت نشد" description="کلاس مورد نظر وجود ندارد یا حذف شده است." />
        </div>
      </div>
    );
  }

  const avgProgress = students.length > 0 
    ? Math.round(students.reduce((acc, s) => acc + s.progress, 0) / students.length)
    : 0;

  const avgGrade = students.length > 0 
    ? (students.reduce((acc, s) => acc + (s.grade || 0), 0) / students.length).toFixed(1)
    : '0';

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => router.back()} className="rounded-full">
            <ArrowRight className="h-5 w-5" />
          </Button>
          <div>
            <p className="text-sm text-muted-foreground">مدیریت دانش‌آموزان</p>
            <h1 className="text-2xl font-bold">{classDetail.title}</h1>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline">
            <Download className="h-4 w-4 ml-2" />
            خروجی اکسل
          </Button>
          <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
            <DialogTrigger asChild>
              <Button>
                <UserPlus className="h-4 w-4 ml-2" />
                افزودن دانش‌آموز
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>افزودن دانش‌آموز جدید</DialogTitle>
                <DialogDescription>
                  ایمیل دانش‌آموز را وارد کنید تا به این کلاس اضافه شود.
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4 py-4">
                <div className="space-y-2">
                  <Label htmlFor="email">ایمیل دانش‌آموز</Label>
                  <Input 
                    id="email" 
                    type="email"
                    placeholder="example@mail.com"
                    value={newStudentEmail}
                    onChange={(e) => setNewStudentEmail(e.target.value)}
                  />
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setIsAddDialogOpen(false)}>
                  انصراف
                </Button>
                <Button onClick={handleAddStudent} disabled={isAdding}>
                  {isAdding ? 'در حال افزودن...' : 'افزودن'}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4">
            <p className="text-sm text-muted-foreground">کل دانش‌آموزان</p>
            <p className="text-2xl font-bold">{students.length}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-sm text-muted-foreground">دانش‌آموزان فعال</p>
            <p className="text-2xl font-bold text-emerald-600">
              {students.filter(s => s.status === 'active').length}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-sm text-muted-foreground">میانگین پیشرفت</p>
            <p className="text-2xl font-bold">{avgProgress}%</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-sm text-muted-foreground">میانگین نمره</p>
            <p className="text-2xl font-bold">{avgGrade}</p>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-col md:flex-row gap-4">
            <div className="relative flex-1">
              <Search className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input 
                placeholder="جستجو در دانش‌آموزان..." 
                className="pr-10"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="icon">
                <Filter className="h-4 w-4" />
              </Button>
              <Button variant="outline" size="icon">
                <SortAsc className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Students Table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">لیست دانش‌آموزان</CardTitle>
          <CardDescription>{filteredStudents.length} دانش‌آموز</CardDescription>
        </CardHeader>
        <CardContent>
          {filteredStudents.length === 0 ? (
            <div className="text-center py-12">
              <UserX className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <p className="text-muted-foreground">دانش‌آموزی یافت نشد</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="text-right">دانش‌آموز</TableHead>
                  <TableHead className="text-right">تاریخ عضویت</TableHead>
                  <TableHead className="text-right">پیشرفت</TableHead>
                  <TableHead className="text-right">نمره</TableHead>
                  <TableHead className="text-right">آخرین فعالیت</TableHead>
                  <TableHead className="text-right">وضعیت</TableHead>
                  <TableHead className="text-left w-12"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredStudents.map(student => (
                  <TableRow key={student.id}>
                    <TableCell>
                      <div className="flex items-center gap-3">
                        <Avatar className="h-9 w-9">
                          <AvatarImage src={student.avatar} alt={student.name} />
                          <AvatarFallback>{student.name.charAt(0)}</AvatarFallback>
                        </Avatar>
                        <div>
                          <p className="font-medium text-sm">{student.name}</p>
                          <p className="text-xs text-muted-foreground">{student.email}</p>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">{student.joinDate}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Progress value={student.progress} className="h-2 w-16" />
                        <span className="text-sm font-medium">{student.progress}%</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <span className="font-medium">{student.grade || '-'}</span>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">{student.lastActivity}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className={statusConfig[student.status]?.color}>
                        {statusConfig[student.status]?.label}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" className="h-8 w-8">
                            <MoreVertical className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="w-48">
                          <DropdownMenuItem>
                            <Mail className="h-4 w-4 ml-2" />
                            ارسال پیام
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem 
                            className="text-destructive focus:text-destructive"
                            onClick={() => handleRemoveStudent(student.id, student.name)}
                          >
                            <Trash2 className="h-4 w-4 ml-2" />
                            حذف از کلاس
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
