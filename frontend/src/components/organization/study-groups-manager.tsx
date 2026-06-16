'use client';

import { useEffect, useState, useCallback } from 'react';
import { OrganizationService } from '@/services/organization-service';
import type { StudyGroup, OrgMembership } from '@/types';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { ErrorState } from '@/components/shared/error-state';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { toast } from 'sonner';
import { Plus, Trash2, Settings2, Users, GraduationCap, X, AlertTriangle } from 'lucide-react';
import { formatPersianNumber } from '@/lib/persian-digits';

const EMPTY_FORM = { name: '', grade_label: '', subject: '', description: '' };

/** Manager UI: create study groups + assign teachers / enroll students. */
export function StudyGroupsManager({ orgId }: { orgId: number }) {
  const [groups, setGroups] = useState<StudyGroup[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [orgTeachers, setOrgTeachers] = useState<OrgMembership[]>([]);
  const [orgStudents, setOrgStudents] = useState<OrgMembership[]>([]);

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [submitting, setSubmitting] = useState(false);

  const [managed, setManaged] = useState<StudyGroup | null>(null);
  const [teacherToAdd, setTeacherToAdd] = useState('');
  const [studentToAdd, setStudentToAdd] = useState('');

  const [deleteTarget, setDeleteTarget] = useState<StudyGroup | null>(null);

  const loadGroups = useCallback(async () => {
    setError(null);
    try {
      setGroups(await OrganizationService.getStudyGroups(orgId));
    } catch {
      setError('خطا در دریافت گروه‌های آموزشی');
    }
  }, [orgId]);

  useEffect(() => {
    loadGroups();
    OrganizationService.getMembers(orgId, { role: 'teacher' }).then(setOrgTeachers).catch(() => {});
    OrganizationService.getMembers(orgId, { role: 'student' }).then(setOrgStudents).catch(() => {});
  }, [orgId, loadGroups]);

  const patchGroupInList = (updated: StudyGroup) =>
    setGroups((gs) => (gs ? gs.map((g) => (g.id === updated.id ? updated : g)) : gs));

  const handleCreate = async () => {
    if (!form.name.trim()) {
      toast.error('نام گروه را وارد کنید.');
      return;
    }
    setSubmitting(true);
    try {
      await OrganizationService.createStudyGroup(orgId, {
        name: form.name.trim(),
        grade_label: form.grade_label.trim(),
        subject: form.subject.trim(),
        description: form.description.trim(),
      });
      toast.success('گروه آموزشی ساخته شد.');
      setIsCreateOpen(false);
      setForm({ ...EMPTY_FORM });
      loadGroups();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'خطا در ساخت گروه');
    } finally {
      setSubmitting(false);
    }
  };

  const refreshManaged = async (groupId: number) => {
    const fresh = await OrganizationService.getStudyGroup(orgId, groupId);
    setManaged(fresh);
    patchGroupInList(fresh);
  };

  const handleAddTeacher = async () => {
    if (!managed || !teacherToAdd) return;
    try {
      const updated = await OrganizationService.assignStudyGroupTeacher(orgId, managed.id, Number(teacherToAdd));
      setManaged(updated);
      patchGroupInList(updated);
      setTeacherToAdd('');
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'خطا در افزودن معلم');
    }
  };

  const handleRemoveTeacher = async (userId: number) => {
    if (!managed) return;
    try {
      await OrganizationService.removeStudyGroupTeacher(orgId, managed.id, userId);
      await refreshManaged(managed.id);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'خطا');
    }
  };

  const handleAddStudent = async () => {
    if (!managed || !studentToAdd) return;
    try {
      const updated = await OrganizationService.addStudyGroupStudent(orgId, managed.id, Number(studentToAdd));
      setManaged(updated);
      patchGroupInList(updated);
      setStudentToAdd('');
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'خطا در افزودن دانش‌آموز');
    }
  };

  const handleRemoveStudent = async (userId: number) => {
    if (!managed) return;
    try {
      await OrganizationService.removeStudyGroupStudent(orgId, managed.id, userId);
      await refreshManaged(managed.id);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'خطا');
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setSubmitting(true);
    try {
      await OrganizationService.deleteStudyGroup(orgId, deleteTarget.id);
      toast.success('گروه حذف شد.');
      setDeleteTarget(null);
      loadGroups();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'خطا');
    } finally {
      setSubmitting(false);
    }
  };

  const managedTeacherIds = new Set((managed?.teachers ?? []).map((t) => t.id));
  const managedStudentIds = new Set((managed?.students ?? []).map((s) => s.id));
  const availableTeachers = orgTeachers.filter((m) => !managedTeacherIds.has(m.userId));
  const availableStudents = orgStudents.filter((m) => !managedStudentIds.has(m.userId));

  return (
    <div className="space-y-4 mt-6">
      {/* Header + create */}
      <div className="flex justify-between items-center">
        <p className="text-sm text-muted-foreground">
          {groups && groups.length > 0 ? `${formatPersianNumber(groups.length)} گروه آموزشی` : ''}
        </p>
        <Dialog
          open={isCreateOpen}
          onOpenChange={(open) => {
            setIsCreateOpen(open);
            if (!open) setForm({ ...EMPTY_FORM });
          }}
        >
          <DialogTrigger asChild>
            <Button className="gap-2 rounded-xl" size="sm">
              <Plus className="w-4 h-4" />
              گروه جدید
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-md" dir="rtl">
            <DialogHeader>
              <DialogTitle>ایجاد گروه آموزشی</DialogTitle>
              <DialogDescription>یک گروه/کلاس‌بندی تازه برای سازمان بسازید (مثلاً «دهم ریاضی»).</DialogDescription>
            </DialogHeader>
            <div className="space-y-4 mt-2">
              <div className="space-y-2">
                <Label>نام گروه *</Label>
                <Input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} placeholder="مثلاً دهم ریاضی" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2">
                  <Label>پایه</Label>
                  <Input value={form.grade_label} onChange={(e) => setForm((f) => ({ ...f, grade_label: e.target.value }))} placeholder="دهم" />
                </div>
                <div className="space-y-2">
                  <Label>درس/رشته</Label>
                  <Input value={form.subject} onChange={(e) => setForm((f) => ({ ...f, subject: e.target.value }))} placeholder="ریاضی" />
                </div>
              </div>
              <div className="space-y-2">
                <Label>توضیحات</Label>
                <Textarea value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} rows={2} />
              </div>
              <DialogFooter>
                <Button className="w-full rounded-xl" onClick={handleCreate} disabled={submitting}>
                  {submitting ? 'در حال ایجاد...' : 'ایجاد گروه'}
                </Button>
              </DialogFooter>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* List */}
      {groups === null && !error ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => <Skeleton key={i} className="h-20 rounded-xl" />)}
        </div>
      ) : error ? (
        <ErrorState title="خطا" description={error} onRetry={loadGroups} />
      ) : groups && groups.length === 0 ? (
        <Card className="rounded-2xl border-dashed">
          <CardContent className="py-16 text-center">
            <GraduationCap className="w-10 h-10 text-muted-foreground mx-auto mb-3" />
            <p className="font-medium">هنوز گروهی ساخته نشده</p>
            <p className="text-xs text-muted-foreground mt-1">با «گروه جدید» اولین گروه آموزشی را بسازید.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2">
          {groups!.map((g) => (
            <Card key={g.id} className="rounded-xl hover:shadow-sm transition-shadow">
              <CardContent className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="text-sm font-bold truncate">{g.name}</p>
                    {g.gradeLabel && <Badge variant="outline" className="text-[10px]">{g.gradeLabel}</Badge>}
                    {g.subject && <Badge variant="outline" className="text-[10px]">{g.subject}</Badge>}
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    {formatPersianNumber(g.teacherCount)} معلم · {formatPersianNumber(g.studentCount)} دانش‌آموز · {formatPersianNumber(g.classCount)} کلاس
                  </p>
                </div>
                <div className="flex items-center gap-2 self-end sm:self-auto">
                  <Button variant="outline" size="sm" className="gap-1.5 rounded-lg" onClick={() => setManaged(g)}>
                    <Settings2 className="w-3.5 h-3.5" />
                    مدیریت
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-destructive hover:text-destructive hover:bg-destructive/10"
                    onClick={() => setDeleteTarget(g)}
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Manage dialog (teachers + students) */}
      <Dialog open={!!managed} onOpenChange={(open) => { if (!open) { setManaged(null); setTeacherToAdd(''); setStudentToAdd(''); } }}>
        <DialogContent className="sm:max-w-lg max-h-[85vh] overflow-y-auto" dir="rtl">
          <DialogHeader>
            <DialogTitle>{managed?.name}</DialogTitle>
            <DialogDescription>تخصیص معلم و افزودن دانش‌آموز به این گروه.</DialogDescription>
          </DialogHeader>

          {/* Teachers */}
          <div className="space-y-3">
            <Label className="flex items-center gap-1.5"><Users className="w-4 h-4" /> معلمان</Label>
            {managed?.teachers && managed.teachers.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {managed.teachers.map((t) => (
                  <Badge key={t.id} variant="secondary" className="gap-1">
                    {t.name}
                    <button type="button" onClick={() => handleRemoveTeacher(t.id)} className="rounded-full p-0.5 hover:bg-foreground/10" title="حذف">
                      <X className="h-3 w-3" />
                    </button>
                  </Badge>
                ))}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">معلمی تخصیص داده نشده.</p>
            )}
            <div className="flex gap-2">
              <Select value={teacherToAdd} onValueChange={setTeacherToAdd}>
                <SelectTrigger className="flex-1"><SelectValue placeholder="انتخاب معلم…" /></SelectTrigger>
                <SelectContent>
                  {availableTeachers.length === 0 ? (
                    <div className="px-2 py-1.5 text-xs text-muted-foreground">معلمی برای افزودن نیست</div>
                  ) : (
                    availableTeachers.map((m) => (
                      <SelectItem key={m.userId} value={String(m.userId)}>{m.userName}</SelectItem>
                    ))
                  )}
                </SelectContent>
              </Select>
              <Button type="button" variant="secondary" onClick={handleAddTeacher} disabled={!teacherToAdd}>افزودن</Button>
            </div>
          </div>

          {/* Students */}
          <div className="space-y-3 pt-2">
            <Label className="flex items-center gap-1.5"><GraduationCap className="w-4 h-4" /> دانش‌آموزان</Label>
            {managed?.students && managed.students.length > 0 ? (
              <div className="space-y-1.5 max-h-48 overflow-y-auto">
                {managed.students.map((s) => (
                  <div key={s.id} className="flex items-center justify-between gap-2 text-sm bg-muted/40 rounded-lg px-3 py-1.5">
                    <span className="truncate">{s.name}</span>
                    <button type="button" onClick={() => handleRemoveStudent(s.id)} className="rounded-full p-1 hover:bg-foreground/10 shrink-0" title="حذف">
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">دانش‌آموزی اضافه نشده.</p>
            )}
            <div className="flex gap-2">
              <Select value={studentToAdd} onValueChange={setStudentToAdd}>
                <SelectTrigger className="flex-1"><SelectValue placeholder="انتخاب دانش‌آموز…" /></SelectTrigger>
                <SelectContent>
                  {availableStudents.length === 0 ? (
                    <div className="px-2 py-1.5 text-xs text-muted-foreground">دانش‌آموزی برای افزودن نیست</div>
                  ) : (
                    availableStudents.map((m) => (
                      <SelectItem key={m.userId} value={String(m.userId)}>{m.userName}</SelectItem>
                    ))
                  )}
                </SelectContent>
              </Select>
              <Button type="button" variant="secondary" onClick={handleAddStudent} disabled={!studentToAdd}>افزودن</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Delete confirm */}
      <Dialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <DialogContent className="sm:max-w-sm" dir="rtl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-destructive">
              <AlertTriangle className="w-5 h-5" />
              حذف گروه آموزشی
            </DialogTitle>
            <DialogDescription>
              آیا از حذف گروه <strong>{deleteTarget?.name}</strong> اطمینان دارید؟ این کار تخصیص‌های معلم و دانش‌آموز این گروه را هم حذف می‌کند.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="flex gap-2 sm:gap-2">
            <Button variant="outline" className="flex-1 rounded-xl" onClick={() => setDeleteTarget(null)}>انصراف</Button>
            <Button variant="destructive" className="flex-1 rounded-xl" onClick={handleDelete} disabled={submitting}>
              {submitting ? 'در حال حذف...' : 'حذف گروه'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
