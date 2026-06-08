'use client';

import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { useWorkspace } from '@/hooks/use-workspace';
import { OrganizationService } from '@/services/organization-service';
import { OrgManagerGuard } from '@/components/organization/org-manager-guard';
import { formatPersianNumber, toPersianDigits } from '@/lib/persian-digits';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
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
  GraduationCap,
  UserPlus,
  Users,
  Mail,
  Phone,
  X,
  Copy,
  Check,
  IdCard,
  PlusCircle,
} from 'lucide-react';
import type { OrgMembership, StudyGroup, InvitationCode } from '@/types';

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

  const [loading, setLoading] = useState(true);
  const [teachers, setTeachers] = useState<OrgMembership[]>([]);
  const [groups, setGroups] = useState<StudyGroup[]>([]);

  // Invite dialog state
  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviteLoading, setInviteLoading] = useState(false);
  const [inviteCode, setInviteCode] = useState<InvitationCode | null>(null);
  const [copied, setCopied] = useState(false);

  // Assign-to-group dialog state
  const [assignFor, setAssignFor] = useState<OrgMembership | null>(null);
  const [assignGroupId, setAssignGroupId] = useState<string>('');
  const [assignLoading, setAssignLoading] = useState(false);

  const load = async () => {
    if (!orgId) return;
    setLoading(true);
    try {
      const [tRes, dRes, aRes, gRes] = await Promise.all([
        OrganizationService.getMembers(orgId, { role: 'teacher' }),
        OrganizationService.getMembers(orgId, { role: 'deputy' }),
        OrganizationService.getMembers(orgId, { role: 'admin' }),
        OrganizationService.getStudyGroups(orgId),
      ]);
      // Merge and dedupe by userId.
      const byUser = new Map<number, OrgMembership>();
      for (const m of [...tRes, ...dRes, ...aRes]) {
        if (!byUser.has(m.userId)) byUser.set(m.userId, m);
      }
      setTeachers(Array.from(byUser.values()));
      setGroups(gRes);
    } catch {
      toast.error('بارگذاری فهرست معلمان ناموفق بود.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (orgId) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orgId]);

  if (!orgId) return null;

  // Groups a given teacher is assigned to (scan groups[].teachers for matching userId).
  const groupsForTeacher = (teacher: OrgMembership) =>
    groups.filter((g) => g.teachers.some((t) => t.id === teacher.userId));

  // Groups a teacher is NOT yet in (for the assign Select).
  const assignableGroups = (teacher: OrgMembership) =>
    groups.filter((g) => !g.teachers.some((t) => t.id === teacher.userId));

  const openInvite = () => {
    setInviteCode(null);
    setCopied(false);
    setInviteOpen(true);
  };

  const handleCreateInvite = async () => {
    if (!orgId) return;
    setInviteLoading(true);
    try {
      const code = await OrganizationService.createInvitationCode(orgId, {
        target_role: 'teacher',
        label: 'کد دعوت معلم',
        max_uses: 1,
      });
      setInviteCode(code);
      toast.success('کد دعوت معلم ساخته شد.');
    } catch {
      toast.error('ساخت کد دعوت ناموفق بود.');
    } finally {
      setInviteLoading(false);
    }
  };

  const handleCopy = async () => {
    if (!inviteCode) return;
    try {
      await navigator.clipboard.writeText(inviteCode.code);
      setCopied(true);
      toast.success('کپی شد');
      setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error('کپی ناموفق بود.');
    }
  };

  const openAssign = (teacher: OrgMembership) => {
    setAssignFor(teacher);
    setAssignGroupId('');
  };

  const handleAssign = async () => {
    if (!orgId || !assignFor || !assignGroupId) return;
    setAssignLoading(true);
    try {
      await OrganizationService.assignTeacherToGroup(
        orgId,
        Number(assignGroupId),
        assignFor.userId,
      );
      toast.success('معلم به گروه تخصیص داده شد.');
      setAssignFor(null);
      setAssignGroupId('');
      await load();
    } catch {
      toast.error('تخصیص معلم به گروه ناموفق بود.');
    } finally {
      setAssignLoading(false);
    }
  };

  const handleUnassign = async (teacher: OrgMembership, group: StudyGroup) => {
    if (!orgId) return;
    try {
      await OrganizationService.unassignTeacherFromGroup(
        orgId,
        group.id,
        teacher.userId,
      );
      toast.success('معلم از گروه حذف شد.');
      await load();
    } catch {
      toast.error('حذف معلم از گروه ناموفق بود.');
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <GraduationCap className="h-6 w-6 text-primary" />
            <h1 className="text-2xl font-bold tracking-tight">معلمان سازمان</h1>
          </div>
          <p className="text-sm text-muted-foreground">
            معلمان سازمان را مدیریت کنید و مشخص کنید هر معلم در کدام گروه‌های
            آموزشی تدریس می‌کند.
          </p>
        </div>
        <Button onClick={openInvite} className="gap-2">
          <UserPlus className="h-4 w-4" />
          دعوت معلم جدید
        </Button>
      </div>

      {/* Content */}
      {loading ? (
        <div className="space-y-4">
          <Skeleton className="h-28 rounded-2xl" />
          <Skeleton className="h-28 rounded-2xl" />
          <Skeleton className="h-28 rounded-2xl" />
        </div>
      ) : teachers.length === 0 ? (
        <Card className="rounded-2xl border-border/50 shadow-sm">
          <CardContent className="flex flex-col items-center justify-center gap-3 py-16 text-center">
            <div className="rounded-full bg-muted p-4">
              <Users className="h-8 w-8 text-muted-foreground" />
            </div>
            <p className="text-base font-medium">هنوز معلمی در سازمان نیست</p>
            <p className="max-w-sm text-sm text-muted-foreground">
              با ساخت کد دعوت، معلمان را به سازمان خود اضافه کنید تا بتوانند
              کلاس‌ها را مدیریت کنند.
            </p>
            <Button onClick={openInvite} variant="outline" className="mt-2 gap-2">
              <UserPlus className="h-4 w-4" />
              دعوت معلم جدید
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            {formatPersianNumber(teachers.length)} معلم در این سازمان
          </p>
          {teachers.map((teacher) => {
            const assigned = groupsForTeacher(teacher);
            const canAssign = assignableGroups(teacher).length > 0;
            return (
              <Card
                key={teacher.id}
                className="rounded-2xl border-border/50 shadow-sm"
              >
                <CardHeader className="pb-3">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="space-y-1">
                      <CardTitle className="flex items-center gap-2 text-lg">
                        {teacher.userName || 'بدون نام'}
                        <Badge variant="secondary" className="font-normal">
                          {teacher.orgRoleDisplay}
                        </Badge>
                      </CardTitle>
                      <div className="flex flex-col gap-1 text-sm text-muted-foreground sm:flex-row sm:flex-wrap sm:gap-x-4">
                        {teacher.userEmail && (
                          <span className="flex items-center gap-1.5">
                            <Mail className="h-3.5 w-3.5" />
                            {teacher.userEmail}
                          </span>
                        )}
                        {teacher.userPhone && (
                          <span className="flex items-center gap-1.5">
                            <Phone className="h-3.5 w-3.5" />
                            {toPersianDigits(teacher.userPhone)}
                          </span>
                        )}
                        {teacher.internalId && (
                          <span className="flex items-center gap-1.5">
                            <IdCard className="h-3.5 w-3.5" />
                            کد داخلی: {toPersianDigits(teacher.internalId)}
                          </span>
                        )}
                      </div>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      className="gap-1.5"
                      onClick={() => openAssign(teacher)}
                      disabled={!canAssign}
                    >
                      <PlusCircle className="h-4 w-4" />
                      تخصیص به گروه
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    <p className="text-xs font-medium text-muted-foreground">
                      گروه‌های آموزشی
                    </p>
                    {assigned.length === 0 ? (
                      <p className="text-sm text-muted-foreground">بدون گروه</p>
                    ) : (
                      <div className="flex flex-wrap gap-2">
                        {assigned.map((group) => (
                          <Badge
                            key={group.id}
                            variant="outline"
                            className="gap-1.5 py-1 pl-1.5 pr-2.5"
                          >
                            <span>{group.name}</span>
                            <button
                              type="button"
                              onClick={() => handleUnassign(teacher, group)}
                              className="rounded-full p-0.5 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
                              aria-label={`حذف ${teacher.userName} از گروه ${group.name}`}
                            >
                              <X className="h-3.5 w-3.5" />
                            </button>
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Invite teacher dialog */}
      <Dialog open={inviteOpen} onOpenChange={setInviteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>دعوت معلم جدید</DialogTitle>
            <DialogDescription>
              {inviteCode
                ? 'کد دعوت معلم ساخته شد. آن را برای معلم ارسال کنید.'
                : 'با تأیید این کادر، یک کد دعوت یک‌بارمصرف برای معلم ساخته می‌شود.'}
            </DialogDescription>
          </DialogHeader>

          {inviteCode ? (
            <div className="space-y-4">
              <div className="rounded-2xl border border-border/50 bg-muted/40 p-4">
                <p className="mb-2 text-xs text-muted-foreground">کد دعوت</p>
                <div className="flex items-center justify-between gap-3">
                  <span className="font-mono text-xl font-bold tracking-widest">
                    {inviteCode.code}
                  </span>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="gap-1.5"
                    onClick={handleCopy}
                  >
                    {copied ? (
                      <Check className="h-4 w-4" />
                    ) : (
                      <Copy className="h-4 w-4" />
                    )}
                    {copied ? 'کپی شد' : 'کپی'}
                  </Button>
                </div>
              </div>
              <p className="text-sm text-muted-foreground">
                معلم با مراجعه به صفحه‌ی پیوستن به سازمان و وارد کردن این کد،
                ثبت‌نام خود را کامل می‌کند. این کد فقط{' '}
                {formatPersianNumber(inviteCode.maxUses)} بار قابل استفاده است.
              </p>
            </div>
          ) : null}

          <DialogFooter>
            {inviteCode ? (
              <DialogClose asChild>
                <Button type="button">بستن</Button>
              </DialogClose>
            ) : (
              <>
                <DialogClose asChild>
                  <Button type="button" variant="outline">
                    انصراف
                  </Button>
                </DialogClose>
                <Button
                  type="button"
                  onClick={handleCreateInvite}
                  disabled={inviteLoading}
                >
                  {inviteLoading ? 'در حال ساخت…' : 'ساخت کد دعوت'}
                </Button>
              </>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Assign-to-group dialog */}
      <Dialog
        open={!!assignFor}
        onOpenChange={(open) => {
          if (!open) {
            setAssignFor(null);
            setAssignGroupId('');
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>تخصیص به گروه</DialogTitle>
            <DialogDescription>
              {assignFor
                ? `انتخاب گروه آموزشی برای ${assignFor.userName || 'این معلم'}`
                : ''}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-2 py-2">
            <p className="text-sm font-medium">گروه آموزشی</p>
            {assignFor && assignableGroups(assignFor).length === 0 ? (
              <p className="text-sm text-muted-foreground">
                این معلم در همه‌ی گروه‌ها عضو است.
              </p>
            ) : (
              <Select value={assignGroupId} onValueChange={setAssignGroupId}>
                <SelectTrigger>
                  <SelectValue placeholder="یک گروه انتخاب کنید" />
                </SelectTrigger>
                <SelectContent>
                  {assignFor &&
                    assignableGroups(assignFor).map((group) => (
                      <SelectItem key={group.id} value={String(group.id)}>
                        {group.name}
                        {group.gradeLabel ? ` — ${group.gradeLabel}` : ''}
                      </SelectItem>
                    ))}
                </SelectContent>
              </Select>
            )}
          </div>

          <DialogFooter>
            <DialogClose asChild>
              <Button type="button" variant="outline">
                انصراف
              </Button>
            </DialogClose>
            <Button
              type="button"
              onClick={handleAssign}
              disabled={!assignGroupId || assignLoading}
            >
              {assignLoading ? 'در حال تخصیص…' : 'تخصیص'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
