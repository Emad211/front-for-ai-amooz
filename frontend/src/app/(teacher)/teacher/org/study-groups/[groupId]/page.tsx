'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { toast } from 'sonner';
import {
  ChevronLeft,
  Pencil,
  Plus,
  X,
  Trash2,
  Users,
  GraduationCap,
  BookOpen,
} from 'lucide-react';
import { useWorkspace } from '@/hooks/use-workspace';
import { OrganizationService } from '@/services/organization-service';
import { OrgManagerGuard } from '@/components/organization/org-manager-guard';
import { formatPersianNumber, toPersianDigits } from '@/lib/persian-digits';
import { formatPersianDate } from '@/lib/date-utils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogClose,
} from '@/components/ui/dialog';
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from '@/components/ui/select';
import {
  Table,
  TableHeader,
  TableBody,
  TableHead,
  TableRow,
  TableCell,
} from '@/components/ui/table';
import type { StudyGroupDetail, OrgMembership } from '@/types';

export default function Page() {
  return (
    <OrgManagerGuard>
      <PageInner />
    </OrgManagerGuard>
  );
}

function PageInner() {
  const { activeWorkspace } = useWorkspace();
  const orgId = activeWorkspace?.id;
  const params = useParams();
  const groupId = Number(params.groupId);

  const [group, setGroup] = useState<StudyGroupDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  // Edit dialog state
  const [editOpen, setEditOpen] = useState(false);
  const [editName, setEditName] = useState('');
  const [editGrade, setEditGrade] = useState('');
  const [editSubject, setEditSubject] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const [editStatus, setEditStatus] = useState<'active' | 'archived'>('active');
  const [editSaving, setEditSaving] = useState(false);

  // Add-teacher dialog state
  const [teacherDialogOpen, setTeacherDialogOpen] = useState(false);
  const [orgTeachers, setOrgTeachers] = useState<OrgMembership[]>([]);
  const [teachersLoading, setTeachersLoading] = useState(false);
  const [selectedTeacher, setSelectedTeacher] = useState<string>('');
  const [teacherSaving, setTeacherSaving] = useState(false);

  // Add-student dialog state
  const [studentDialogOpen, setStudentDialogOpen] = useState(false);
  const [orgStudents, setOrgStudents] = useState<OrgMembership[]>([]);
  const [studentsLoading, setStudentsLoading] = useState(false);
  const [selectedStudent, setSelectedStudent] = useState<string>('');
  const [studentSaving, setStudentSaving] = useState(false);

  async function load() {
    if (!orgId) return;
    try {
      setLoading(true);
      setNotFound(false);
      const data = await OrganizationService.getStudyGroup(orgId, groupId);
      setGroup(data);
    } catch {
      setNotFound(true);
      setGroup(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (orgId) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orgId, groupId]);

  if (!orgId) return null;

  // --- Edit ---------------------------------------------------------------
  function openEdit() {
    if (!group) return;
    setEditName(group.name);
    setEditGrade(group.gradeLabel ?? '');
    setEditSubject(group.subject ?? '');
    setEditDescription(group.description ?? '');
    setEditStatus(group.status);
    setEditOpen(true);
  }

  async function submitEdit() {
    if (!orgId) return;
    if (!editName.trim()) {
      toast.error('نام گروه را وارد کنید.');
      return;
    }
    try {
      setEditSaving(true);
      await OrganizationService.updateStudyGroup(orgId, groupId, {
        name: editName.trim(),
        grade_label: editGrade.trim(),
        subject: editSubject.trim(),
        description: editDescription.trim(),
        status: editStatus,
      });
      toast.success('گروه آموزشی به‌روزرسانی شد.');
      setEditOpen(false);
      await load();
    } catch {
      toast.error('به‌روزرسانی گروه ناموفق بود.');
    } finally {
      setEditSaving(false);
    }
  }

  // --- Teachers -----------------------------------------------------------
  async function openTeacherDialog() {
    setSelectedTeacher('');
    setTeacherDialogOpen(true);
    if (!orgId) return;
    try {
      setTeachersLoading(true);
      const [teachers, deputies, admins] = await Promise.all([
        OrganizationService.getMembers(orgId, { role: 'teacher' }),
        OrganizationService.getMembers(orgId, { role: 'deputy' }),
        OrganizationService.getMembers(orgId, { role: 'admin' }),
      ]);
      // Merge + de-duplicate by userId (managers can also teach).
      const merged = [...teachers, ...deputies, ...admins];
      const seen = new Set<number>();
      const unique = merged.filter((m) => {
        if (seen.has(m.userId)) return false;
        seen.add(m.userId);
        return true;
      });
      setOrgTeachers(unique);
    } catch {
      toast.error('دریافت فهرست معلمان ناموفق بود.');
      setOrgTeachers([]);
    } finally {
      setTeachersLoading(false);
    }
  }

  async function assignTeacher() {
    if (!orgId || !selectedTeacher) return;
    try {
      setTeacherSaving(true);
      await OrganizationService.assignTeacherToGroup(orgId, groupId, Number(selectedTeacher));
      toast.success('معلم به گروه افزوده شد.');
      setTeacherDialogOpen(false);
      await load();
    } catch {
      toast.error('افزودن معلم ناموفق بود.');
    } finally {
      setTeacherSaving(false);
    }
  }

  async function unassignTeacher(userId: number) {
    if (!orgId) return;
    try {
      await OrganizationService.unassignTeacherFromGroup(orgId, groupId, userId);
      toast.success('معلم از گروه حذف شد.');
      await load();
    } catch {
      toast.error('حذف معلم ناموفق بود.');
    }
  }

  // --- Students -----------------------------------------------------------
  async function openStudentDialog() {
    setSelectedStudent('');
    setStudentDialogOpen(true);
    if (!orgId) return;
    try {
      setStudentsLoading(true);
      const students = await OrganizationService.getMembers(orgId, { role: 'student' });
      setOrgStudents(students);
    } catch {
      toast.error('دریافت فهرست دانش‌آموزان ناموفق بود.');
      setOrgStudents([]);
    } finally {
      setStudentsLoading(false);
    }
  }

  async function addStudent() {
    if (!orgId || !selectedStudent) return;
    try {
      setStudentSaving(true);
      await OrganizationService.addStudentToGroup(orgId, groupId, Number(selectedStudent));
      toast.success('دانش‌آموز به گروه افزوده شد.');
      setStudentDialogOpen(false);
      await load();
    } catch {
      toast.error('افزودن دانش‌آموز ناموفق بود.');
    } finally {
      setStudentSaving(false);
    }
  }

  async function removeStudent(userId: number) {
    if (!orgId) return;
    try {
      await OrganizationService.removeStudentFromGroup(orgId, groupId, userId);
      toast.success('دانش‌آموز از گروه حذف شد.');
      await load();
    } catch {
      toast.error('حذف دانش‌آموز ناموفق بود.');
    }
  }

  // --- Loading / not-found ------------------------------------------------
  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-56" />
        <Skeleton className="h-28 rounded-2xl" />
        <Skeleton className="h-64 rounded-2xl" />
        <Skeleton className="h-48 rounded-2xl" />
      </div>
    );
  }

  if (notFound || !group) {
    return (
      <div className="flex flex-col items-center justify-center text-center gap-4 py-16">
        <h2 className="text-xl font-bold text-foreground">گروه آموزشی یافت نشد</h2>
        <p className="text-sm text-muted-foreground max-w-md">
          این گروه آموزشی وجود ندارد یا حذف شده است.
        </p>
        <Button asChild variant="outline">
          <Link href="/teacher/org/study-groups">
            <ChevronLeft className="ms-1 h-4 w-4" />
            گروه‌های آموزشی
          </Link>
        </Button>
      </div>
    );
  }

  const assignedTeacherIds = new Set(group.teachers.map((t) => t.id));
  const inGroupStudentIds = new Set(group.students.map((s) => s.id));
  const availableTeachers = orgTeachers.filter((m) => !assignedTeacherIds.has(m.userId));
  const availableStudents = orgStudents.filter((m) => !inGroupStudentIds.has(m.userId));

  return (
    <div className="space-y-6">
      {/* Back link */}
      <Link
        href="/teacher/org/study-groups"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ChevronLeft className="h-4 w-4" />
        گروه‌های آموزشی
      </Link>

      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-2">
          <h1 className="text-2xl font-bold text-foreground">{group.name}</h1>
          <div className="flex flex-wrap items-center gap-2">
            {group.gradeLabel ? <Badge variant="secondary">{group.gradeLabel}</Badge> : null}
            {group.subject ? <Badge variant="secondary">{group.subject}</Badge> : null}
            <Badge variant={group.status === 'active' ? 'default' : 'outline'}>
              {group.statusDisplay}
            </Badge>
          </div>
          {group.description ? (
            <p className="text-sm text-muted-foreground max-w-2xl">{group.description}</p>
          ) : null}
        </div>
        <Button variant="outline" onClick={openEdit}>
          <Pencil className="ms-1 h-4 w-4" />
          ویرایش
        </Button>
      </div>

      {/* Counts */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card className="rounded-2xl border-border/50 shadow-sm">
          <CardContent className="flex items-center gap-3 p-5">
            <div className="h-11 w-11 rounded-xl bg-primary/10 flex items-center justify-center">
              <GraduationCap className="h-5 w-5 text-primary" />
            </div>
            <div>
              <p className="text-xs text-muted-foreground">معلمان</p>
              <p className="text-lg font-bold text-foreground">
                {formatPersianNumber(group.teacherCount)}
              </p>
            </div>
          </CardContent>
        </Card>
        <Card className="rounded-2xl border-border/50 shadow-sm">
          <CardContent className="flex items-center gap-3 p-5">
            <div className="h-11 w-11 rounded-xl bg-primary/10 flex items-center justify-center">
              <Users className="h-5 w-5 text-primary" />
            </div>
            <div>
              <p className="text-xs text-muted-foreground">دانش‌آموزان</p>
              <p className="text-lg font-bold text-foreground">
                {formatPersianNumber(group.studentCount)}
              </p>
            </div>
          </CardContent>
        </Card>
        <Card className="rounded-2xl border-border/50 shadow-sm">
          <CardContent className="flex items-center gap-3 p-5">
            <div className="h-11 w-11 rounded-xl bg-primary/10 flex items-center justify-center">
              <BookOpen className="h-5 w-5 text-primary" />
            </div>
            <div>
              <p className="text-xs text-muted-foreground">کلاس‌ها</p>
              <p className="text-lg font-bold text-foreground">
                {formatPersianNumber(group.classCount)}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Teachers */}
      <Card className="rounded-2xl border-border/50 shadow-sm">
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <CardTitle className="text-base">معلمان گروه</CardTitle>
          <Button size="sm" variant="outline" onClick={openTeacherDialog}>
            <Plus className="ms-1 h-4 w-4" />
            افزودن معلم
          </Button>
        </CardHeader>
        <CardContent>
          {group.teachers.length === 0 ? (
            <p className="text-sm text-muted-foreground py-2">معلمی به این گروه اختصاص نیافته است.</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {group.teachers.map((t) => (
                <span
                  key={t.id}
                  className="inline-flex items-center gap-1 rounded-full bg-muted px-3 py-1 text-sm text-foreground"
                >
                  {t.name}
                  <button
                    type="button"
                    onClick={() => unassignTeacher(t.id)}
                    className="text-muted-foreground hover:text-destructive transition-colors"
                    aria-label={`حذف ${t.name}`}
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </span>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Students */}
      <Card className="rounded-2xl border-border/50 shadow-sm">
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <CardTitle className="text-base">دانش‌آموزان گروه</CardTitle>
          <Button size="sm" variant="outline" onClick={openStudentDialog}>
            <Plus className="ms-1 h-4 w-4" />
            افزودن دانش‌آموز
          </Button>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>نام</TableHead>
                <TableHead>موبایل</TableHead>
                <TableHead>تاریخ عضویت</TableHead>
                <TableHead className="w-12"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {group.students.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-sm text-muted-foreground py-6">
                    دانش‌آموزی در این گروه نیست
                  </TableCell>
                </TableRow>
              ) : (
                group.students.map((s) => (
                  <TableRow key={s.membershipId}>
                    <TableCell className="font-medium">{s.name}</TableCell>
                    <TableCell>{s.phone ? toPersianDigits(s.phone) : '—'}</TableCell>
                    <TableCell>{formatPersianDate(s.joinedAt)}</TableCell>
                    <TableCell>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-8 w-8 text-muted-foreground hover:text-destructive"
                        onClick={() => removeStudent(s.id)}
                        aria-label={`حذف ${s.name}`}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Courses */}
      <Card className="rounded-2xl border-border/50 shadow-sm">
        <CardHeader>
          <CardTitle className="text-base">کلاس‌های ساخته‌شده برای گروه</CardTitle>
        </CardHeader>
        <CardContent>
          {group.courses.length === 0 ? (
            <p className="text-sm text-muted-foreground py-2">هنوز کلاسی برای این گروه ساخته نشده</p>
          ) : (
            <div className="space-y-2">
              {group.courses.map((c) => (
                <div
                  key={c.id}
                  className="flex items-center justify-between gap-3 rounded-xl border border-border/50 px-4 py-3"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-foreground">{c.title}</p>
                    <p className="truncate text-xs text-muted-foreground">{c.teacherName}</p>
                  </div>
                  <Badge variant={c.isPublished ? 'default' : 'outline'} className="shrink-0">
                    {c.isPublished ? 'منتشر شده' : 'پیش‌نویس'}
                  </Badge>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Edit dialog */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>ویرایش گروه آموزشی</DialogTitle>
            <DialogDescription>مشخصات گروه را به‌روزرسانی کنید.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="edit-name">نام گروه</Label>
              <Input
                id="edit-name"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                placeholder="نام گروه"
              />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="edit-grade">پایه</Label>
                <Input
                  id="edit-grade"
                  value={editGrade}
                  onChange={(e) => setEditGrade(e.target.value)}
                  placeholder="مثلاً پایه دهم"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit-subject">درس</Label>
                <Input
                  id="edit-subject"
                  value={editSubject}
                  onChange={(e) => setEditSubject(e.target.value)}
                  placeholder="مثلاً ریاضی"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-description">توضیحات</Label>
              <Textarea
                id="edit-description"
                value={editDescription}
                onChange={(e) => setEditDescription(e.target.value)}
                placeholder="توضیحات گروه"
                rows={3}
              />
            </div>
            <div className="space-y-2">
              <Label>وضعیت</Label>
              <Select
                value={editStatus}
                onValueChange={(v) => setEditStatus(v as 'active' | 'archived')}
              >
                <SelectTrigger>
                  <SelectValue placeholder="وضعیت گروه" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="active">فعال</SelectItem>
                  <SelectItem value="archived">بایگانی‌شده</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline">انصراف</Button>
            </DialogClose>
            <Button onClick={submitEdit} disabled={editSaving}>
              {editSaving ? 'در حال ذخیره…' : 'ذخیره'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Add-teacher dialog */}
      <Dialog open={teacherDialogOpen} onOpenChange={setTeacherDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>افزودن معلم</DialogTitle>
            <DialogDescription>یک معلم را برای اختصاص به این گروه انتخاب کنید.</DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label>معلم</Label>
            {teachersLoading ? (
              <Skeleton className="h-10 w-full rounded-md" />
            ) : (
              <Select value={selectedTeacher} onValueChange={setSelectedTeacher}>
                <SelectTrigger>
                  <SelectValue placeholder="انتخاب معلم" />
                </SelectTrigger>
                <SelectContent>
                  {availableTeachers.length === 0 ? (
                    <div className="px-3 py-2 text-sm text-muted-foreground">
                      معلم قابل‌افزودنی وجود ندارد.
                    </div>
                  ) : (
                    availableTeachers.map((m) => (
                      <SelectItem key={m.userId} value={String(m.userId)}>
                        {m.userName}
                      </SelectItem>
                    ))
                  )}
                </SelectContent>
              </Select>
            )}
          </div>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline">انصراف</Button>
            </DialogClose>
            <Button onClick={assignTeacher} disabled={teacherSaving || !selectedTeacher}>
              {teacherSaving ? 'در حال افزودن…' : 'افزودن'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Add-student dialog */}
      <Dialog open={studentDialogOpen} onOpenChange={setStudentDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>افزودن دانش‌آموز</DialogTitle>
            <DialogDescription>یک دانش‌آموز را برای افزودن به این گروه انتخاب کنید.</DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label>دانش‌آموز</Label>
            {studentsLoading ? (
              <Skeleton className="h-10 w-full rounded-md" />
            ) : (
              <Select value={selectedStudent} onValueChange={setSelectedStudent}>
                <SelectTrigger>
                  <SelectValue placeholder="انتخاب دانش‌آموز" />
                </SelectTrigger>
                <SelectContent>
                  {availableStudents.length === 0 ? (
                    <div className="px-3 py-2 text-sm text-muted-foreground">
                      دانش‌آموز قابل‌افزودنی وجود ندارد.
                    </div>
                  ) : (
                    availableStudents.map((m) => (
                      <SelectItem key={m.userId} value={String(m.userId)}>
                        {m.userName}
                      </SelectItem>
                    ))
                  )}
                </SelectContent>
              </Select>
            )}
          </div>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline">انصراف</Button>
            </DialogClose>
            <Button onClick={addStudent} disabled={studentSaving || !selectedStudent}>
              {studentSaving ? 'در حال افزودن…' : 'افزودن'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
