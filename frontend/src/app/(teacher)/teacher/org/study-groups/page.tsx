'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { useWorkspace } from '@/hooks/use-workspace';
import { OrganizationService } from '@/services/organization-service';
import { OrgManagerGuard } from '@/components/organization/org-manager-guard';
import { formatPersianNumber } from '@/lib/persian-digits';
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
} from '@/components/ui/dialog';
import {
  AlertDialog,
  AlertDialogTrigger,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogAction,
  AlertDialogCancel,
} from '@/components/ui/alert-dialog';
import { GraduationCap, Plus, Trash2, Users, BookOpen, Layers } from 'lucide-react';
import type { StudyGroup } from '@/types';

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

  const [groups, setGroups] = useState<StudyGroup[]>([]);
  const [loading, setLoading] = useState(true);

  // Create dialog state
  const [createOpen, setCreateOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [name, setName] = useState('');
  const [gradeLabel, setGradeLabel] = useState('');
  const [subject, setSubject] = useState('');
  const [description, setDescription] = useState('');

  // Delete state
  const [deletingId, setDeletingId] = useState<number | null>(null);

  async function load() {
    if (!orgId) return;
    setLoading(true);
    try {
      const data = await OrganizationService.getStudyGroups(orgId);
      setGroups(data);
    } catch {
      toast.error('دریافت گروه‌های آموزشی با خطا مواجه شد');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (orgId) load();
    // eslint-disable-next-line
  }, [orgId]);

  if (!orgId) return null;

  function resetForm() {
    setName('');
    setGradeLabel('');
    setSubject('');
    setDescription('');
  }

  async function handleCreate() {
    if (!orgId) return;
    if (!name.trim()) {
      toast.error('نام گروه را وارد کنید');
      return;
    }
    setSaving(true);
    try {
      await OrganizationService.createStudyGroup(orgId, {
        name: name.trim(),
        grade_label: gradeLabel.trim() || undefined,
        subject: subject.trim() || undefined,
        description: description.trim() || undefined,
      });
      toast.success('گروه ساخته شد');
      setCreateOpen(false);
      resetForm();
      await load();
    } catch {
      toast.error('ساخت گروه با خطا مواجه شد');
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(groupId: number) {
    if (!orgId) return;
    setDeletingId(groupId);
    try {
      await OrganizationService.deleteStudyGroup(orgId, groupId);
      toast.success('گروه حذف شد');
      await load();
    } catch {
      toast.error('حذف گروه با خطا مواجه شد');
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="space-y-6">
      {/* Title row */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-1">
          <h1 className="flex items-center gap-2 text-2xl font-bold">
            <GraduationCap className="h-6 w-6 text-primary" />
            گروه‌های آموزشی
          </h1>
          <p className="text-sm text-muted-foreground">
            دسته‌بندی دانش‌آموزان و معلمان در گروه‌های کلاسی
          </p>
        </div>

        <Dialog
          open={createOpen}
          onOpenChange={(open) => {
            setCreateOpen(open);
            if (!open) resetForm();
          }}
        >
          <Button onClick={() => setCreateOpen(true)} className="gap-2">
            <Plus className="h-4 w-4" />
            ایجاد گروه جدید
          </Button>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>ایجاد گروه جدید</DialogTitle>
              <DialogDescription>
                یک گروه آموزشی تازه برای دسته‌بندی دانش‌آموزان و معلمان بسازید.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4 py-2">
              <div className="space-y-2">
                <Label htmlFor="group-name">
                  نام گروه <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="group-name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="دهم ریاضی"
                />
              </div>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="group-grade">پایه</Label>
                  <Input
                    id="group-grade"
                    value={gradeLabel}
                    onChange={(e) => setGradeLabel(e.target.value)}
                    placeholder="دهم"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="group-subject">درس</Label>
                  <Input
                    id="group-subject"
                    value={subject}
                    onChange={(e) => setSubject(e.target.value)}
                    placeholder="ریاضی"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="group-description">توضیحات</Label>
                <Textarea
                  id="group-description"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="توضیحات اختیاری درباره این گروه"
                  rows={3}
                />
              </div>
            </div>

            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setCreateOpen(false)}
                disabled={saving}
              >
                انصراف
              </Button>
              <Button onClick={handleCreate} disabled={saving}>
                {saving ? 'در حال ذخیره...' : 'ساخت گروه'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {/* List */}
      {loading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Skeleton className="h-28 rounded-2xl" />
          <Skeleton className="h-28 rounded-2xl" />
          <Skeleton className="h-28 rounded-2xl" />
        </div>
      ) : groups.length === 0 ? (
        <Card className="rounded-2xl border-border/50 shadow-sm">
          <CardContent className="flex flex-col items-center justify-center gap-3 py-12 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted">
              <GraduationCap className="h-6 w-6 text-muted-foreground" />
            </div>
            <p className="font-medium">هنوز گروهی ساخته نشده است</p>
            <p className="text-sm text-muted-foreground">
              برای شروع، اولین گروه آموزشی خود را بسازید.
            </p>
            <Button onClick={() => setCreateOpen(true)} className="mt-2 gap-2">
              <Plus className="h-4 w-4" />
              ایجاد گروه جدید
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {groups.map((g) => (
            <Card
              key={g.id}
              className="group relative rounded-2xl border-border/50 shadow-sm transition-shadow hover:shadow-md"
            >
              {/* Delete button (above the link layer) */}
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="absolute left-3 top-3 z-10 h-8 w-8 text-muted-foreground hover:text-destructive"
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                    }}
                    aria-label="حذف گروه"
                    disabled={deletingId === g.id}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>حذف گروه؟</AlertDialogTitle>
                    <AlertDialogDescription>
                      با حذف گروه «{g.name}» تمام تخصیص‌های دانش‌آموزان و معلمان آن
                      برداشته می‌شود. این عمل قابل بازگشت نیست.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>انصراف</AlertDialogCancel>
                    <AlertDialogAction
                      onClick={() => handleDelete(g.id)}
                      className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                    >
                      حذف گروه
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>

              <Link
                href={`/teacher/org/study-groups/${g.id}`}
                className="block rounded-2xl focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between gap-2 pl-8">
                    <CardTitle className="text-base font-bold leading-6">
                      {g.name}
                    </CardTitle>
                    <Badge
                      variant={g.status === 'active' ? 'secondary' : 'outline'}
                      className="shrink-0"
                    >
                      {g.statusDisplay}
                    </Badge>
                  </div>
                  {(g.gradeLabel || g.subject) && (
                    <div className="flex flex-wrap gap-1.5 pt-1">
                      {g.gradeLabel && (
                        <Badge variant="outline" className="text-xs font-normal">
                          {g.gradeLabel}
                        </Badge>
                      )}
                      {g.subject && (
                        <Badge variant="outline" className="text-xs font-normal">
                          {g.subject}
                        </Badge>
                      )}
                    </div>
                  )}
                </CardHeader>
                <CardContent>
                  <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-muted-foreground">
                    <span className="flex items-center gap-1.5">
                      <Users className="h-4 w-4" />
                      {formatPersianNumber(g.studentCount)} دانش‌آموز
                    </span>
                    <span className="flex items-center gap-1.5">
                      <GraduationCap className="h-4 w-4" />
                      {formatPersianNumber(g.teacherCount)} معلم
                    </span>
                    <span className="flex items-center gap-1.5">
                      <Layers className="h-4 w-4" />
                      {formatPersianNumber(g.classCount)} کلاس
                    </span>
                  </div>
                </CardContent>
              </Link>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
