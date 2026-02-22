'use client';

import { use, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useOrgDashboard, useOrgMembers, useInvitationCodes } from '@/hooks/use-organizations';
import { OrganizationService } from '@/services/organization-service';
import { PageTransition } from '@/components/ui/page-transition';
import { ErrorState } from '@/components/shared/error-state';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent } from '@/components/ui/card';
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
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { toast } from 'sonner';
import {
  Users,
  BookOpen,
  KeyRound,
  Copy,
  Trash2,
  Building2,
  Plus,
  Search,
  Power,
  PowerOff,
  ChevronRight,
  GraduationCap,
  UserCog,
  AlertTriangle,
} from 'lucide-react';
import type { OrgRole } from '@/types';

const ROLE_OPTIONS = [
  { value: 'admin', label: 'مدیر' },
  { value: 'deputy', label: 'معاون' },
  { value: 'teacher', label: 'معلم' },
  { value: 'student', label: 'دانش‌آموز' },
] as const;

export default function OrganizationDetailPage({
  params: paramsPromise,
}: {
  params: Promise<{ id: string }>;
}) {
  const router = useRouter();
  const params = use(paramsPromise);
  const orgId = parseInt(params.id);

  const { dashboard, isLoading: dashLoading, error: dashError, reload: reloadDash } = useOrgDashboard(orgId);
  const {
    members,
    isLoading: membersLoading,
    error: membersError,
    roleFilter,
    setRoleFilter,
    search,
    setSearch,
    reload: reloadMembers,
  } = useOrgMembers(orgId);
  const { codes, isLoading: codesLoading, error: codesError, reload: reloadCodes } = useInvitationCodes(orgId);

  // ── Create Code Dialog ──
  const [isCreateCodeOpen, setIsCreateCodeOpen] = useState(false);
  const [codeRole, setCodeRole] = useState<OrgRole>('student');
  const [codeLabel, setCodeLabel] = useState('');
  const [codeMaxUses, setCodeMaxUses] = useState('30');
  const [codeCustom, setCodeCustom] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // ── Delete member confirmation ──
  const [deleteMemberTarget, setDeleteMemberTarget] = useState<{ id: number; name: string } | null>(null);

  const resetCodeForm = useCallback(() => {
    setCodeRole('student');
    setCodeLabel('');
    setCodeMaxUses('30');
    setCodeCustom('');
  }, []);

  const handleCreateCode = async () => {
    try {
      setIsSubmitting(true);
      const created = await OrganizationService.createInvitationCode(orgId, {
        target_role: codeRole,
        label: codeLabel.trim(),
        max_uses: parseInt(codeMaxUses) || 30,
        custom_code: codeCustom.trim() || undefined,
      });
      toast.success(`کد دعوت ایجاد شد: ${created.code}`);
      setIsCreateCodeOpen(false);
      resetCodeForm();
      reloadCodes();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در ایجاد کد');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleToggleCode = async (codeId: number, currentActive: boolean) => {
    try {
      await OrganizationService.updateInvitationCode(orgId, codeId, { is_active: !currentActive });
      toast.success(currentActive ? 'کد غیرفعال شد.' : 'کد فعال شد.');
      reloadCodes();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا');
    }
  };

  const handleDeleteCode = async (codeId: number) => {
    try {
      await OrganizationService.deleteInvitationCode(orgId, codeId);
      toast.success('کد حذف شد.');
      reloadCodes();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا');
    }
  };

  const handleRemoveMember = async () => {
    if (!deleteMemberTarget) return;
    try {
      setIsSubmitting(true);
      await OrganizationService.removeMember(orgId, deleteMemberTarget.id);
      toast.success('عضو از سازمان حذف شد.');
      setDeleteMemberTarget(null);
      reloadMembers();
      reloadDash();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleUpdateRole = async (membershipId: number, newRole: OrgRole) => {
    try {
      await OrganizationService.updateMember(orgId, membershipId, { org_role: newRole });
      toast.success('نقش به‌روزرسانی شد.');
      reloadMembers();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا');
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success('کپی شد!');
  };

  // ── Loading ──
  if (dashLoading) {
    return (
      <PageTransition>
        <div className="space-y-8">
          <div className="flex items-center gap-3">
            <Skeleton className="w-12 h-12 rounded-xl" />
            <div className="space-y-2">
              <Skeleton className="h-8 w-48" />
              <Skeleton className="h-4 w-32" />
            </div>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[1, 2, 3, 4].map((i) => (
              <Skeleton key={i} className="h-24 rounded-2xl" />
            ))}
          </div>
          <Skeleton className="h-96 rounded-2xl" />
        </div>
      </PageTransition>
    );
  }

  if (dashError || !dashboard) {
    return (
      <PageTransition>
        <div className="flex items-center justify-center h-[60vh] px-4">
          <div className="w-full max-w-2xl">
            <ErrorState title="خطا" description={dashError || 'سازمان یافت نشد'} onRetry={reloadDash} />
          </div>
        </div>
      </PageTransition>
    );
  }

  const org = dashboard.organization;
  const stats = dashboard.stats;
  const capacityPercent = stats.studentCapacity
    ? Math.round((stats.students / stats.studentCapacity) * 100)
    : 0;

  return (
    <PageTransition>
      <div className="space-y-8">
        {/* ── Breadcrumb + Header ── */}
        <div>
          <button
            onClick={() => router.push('/admin/organizations')}
            className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors mb-4"
          >
            <ChevronRight className="w-4 h-4" />
            بازگشت به لیست سازمان‌ها
          </button>
          <div className="flex items-center gap-4">
            {org.logo ? (
              <img src={org.logo} alt={org.name} className="w-14 h-14 rounded-xl object-cover ring-1 ring-border" />
            ) : (
              <div className="w-14 h-14 rounded-xl bg-primary/10 flex items-center justify-center">
                <Building2 className="w-7 h-7 text-primary" />
              </div>
            )}
            <div>
              <h1 className="text-2xl md:text-3xl font-black text-foreground">{org.name}</h1>
              <p className="text-sm text-muted-foreground font-mono" dir="ltr">
                {org.slug}
              </p>
            </div>
          </div>
        </div>

        {/* ── Stats Cards ── */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card className="rounded-2xl">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center shrink-0">
                  <Users className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                </div>
                <div>
                  <p className="text-2xl font-black">{stats.totalMembers}</p>
                  <p className="text-xs text-muted-foreground">کل اعضا</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card className="rounded-2xl">
            <CardContent className="p-4 space-y-2">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-emerald-500/10 flex items-center justify-center shrink-0">
                  <GraduationCap className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
                </div>
                <div>
                  <p className="text-2xl font-black tabular-nums">
                    {stats.students}
                    <span className="text-sm font-normal text-muted-foreground">/{stats.studentCapacity}</span>
                  </p>
                  <p className="text-xs text-muted-foreground">دانش‌آموزان</p>
                </div>
              </div>
              <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${
                    capacityPercent >= 90
                      ? 'bg-red-500'
                      : capacityPercent >= 70
                        ? 'bg-amber-500'
                        : 'bg-emerald-500'
                  }`}
                  style={{ width: `${Math.min(capacityPercent, 100)}%` }}
                />
              </div>
            </CardContent>
          </Card>
          <Card className="rounded-2xl">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-amber-500/10 flex items-center justify-center shrink-0">
                  <BookOpen className="w-5 h-5 text-amber-600 dark:text-amber-400" />
                </div>
                <div>
                  <p className="text-2xl font-black tabular-nums">
                    {stats.publishedClasses}
                    <span className="text-sm font-normal text-muted-foreground">/{stats.totalClasses}</span>
                  </p>
                  <p className="text-xs text-muted-foreground">کلاس‌ها</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card className="rounded-2xl">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-purple-500/10 flex items-center justify-center shrink-0">
                  <KeyRound className="w-5 h-5 text-purple-600 dark:text-purple-400" />
                </div>
                <div>
                  <p className="text-2xl font-black">{stats.activeInviteCodes}</p>
                  <p className="text-xs text-muted-foreground">کد فعال</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* ── Tabs ── */}
        <Tabs defaultValue="members" dir="rtl">
          <TabsList className="rounded-xl">
            <TabsTrigger value="members" className="gap-1.5 rounded-lg">
              <UserCog className="w-4 h-4" />
              اعضا ({stats.totalMembers})
            </TabsTrigger>
            <TabsTrigger value="codes" className="gap-1.5 rounded-lg">
              <KeyRound className="w-4 h-4" />
              کدهای دعوت
            </TabsTrigger>
          </TabsList>

          {/* ═════ Members Tab ═════ */}
          <TabsContent value="members" className="space-y-4 mt-6">
            <div className="flex flex-col sm:flex-row gap-3">
              <div className="relative flex-1">
                <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  placeholder="جستجوی نام، ایمیل یا شناسه..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="pr-9 rounded-xl"
                />
              </div>
              <Select value={roleFilter} onValueChange={(v) => setRoleFilter(v as OrgRole | '')}>
                <SelectTrigger className="w-[150px] rounded-xl">
                  <SelectValue placeholder="همه نقش‌ها" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="">همه نقش‌ها</SelectItem>
                  {ROLE_OPTIONS.map((r) => (
                    <SelectItem key={r.value} value={r.value}>
                      {r.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {membersLoading ? (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <Skeleton key={i} className="h-16 rounded-xl" />
                ))}
              </div>
            ) : membersError ? (
              <ErrorState title="خطا" description={membersError} onRetry={reloadMembers} />
            ) : members.length === 0 ? (
              <Card className="rounded-2xl border-dashed">
                <CardContent className="py-16 text-center">
                  <Users className="w-10 h-10 text-muted-foreground mx-auto mb-3" />
                  <p className="font-medium">هنوز عضوی ندارد</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    از تب «کدهای دعوت» کد بسازید و به اعضا بدهید.
                  </p>
                </CardContent>
              </Card>
            ) : (
              <div className="space-y-2">
                {members.map((m) => (
                  <Card key={m.id} className="rounded-xl hover:shadow-sm transition-shadow">
                    <CardContent className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="w-10 h-10 rounded-full bg-gradient-to-br from-primary/20 to-primary/5 flex items-center justify-center text-sm font-bold text-primary shrink-0">
                          {m.userName?.charAt(0)?.toUpperCase() || '?'}
                        </div>
                        <div className="min-w-0">
                          <p className="text-sm font-semibold truncate">{m.userName}</p>
                          <p className="text-xs text-muted-foreground truncate">
                            {m.userEmail || m.userPhone || '—'}
                            {m.internalId && (
                              <span className="text-foreground/50"> · {m.internalId}</span>
                            )}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 self-end sm:self-auto">
                        <Select
                          value={m.orgRole}
                          onValueChange={(v) => handleUpdateRole(m.id, v as OrgRole)}
                        >
                          <SelectTrigger className="w-[110px] h-8 rounded-lg text-xs">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {ROLE_OPTIONS.map((r) => (
                              <SelectItem key={r.value} value={r.value}>
                                {r.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <Badge
                          variant={m.status === 'active' ? 'default' : 'destructive'}
                          className="text-[10px] h-6"
                        >
                          {m.statusDisplay}
                        </Badge>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-destructive hover:text-destructive hover:bg-destructive/10"
                          onClick={() => setDeleteMemberTarget({ id: m.id, name: m.userName })}
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </TabsContent>

          {/* ═════ Invitation Codes Tab ═════ */}
          <TabsContent value="codes" className="space-y-4 mt-6">
            <div className="flex justify-between items-center">
              <p className="text-sm text-muted-foreground">
                {codes.length > 0 ? `${codes.length} کد دعوت` : ''}
              </p>
              <Dialog
                open={isCreateCodeOpen}
                onOpenChange={(open) => {
                  setIsCreateCodeOpen(open);
                  if (!open) resetCodeForm();
                }}
              >
                <DialogTrigger asChild>
                  <Button className="gap-2 rounded-xl" size="sm">
                    <Plus className="w-4 h-4" />
                    کد جدید
                  </Button>
                </DialogTrigger>
                <DialogContent className="sm:max-w-md" dir="rtl">
                  <DialogHeader>
                    <DialogTitle>ایجاد کد دعوت</DialogTitle>
                    <DialogDescription>
                      این کد را می‌توانید بین اعضا پخش کنید تا عضو سازمان شوند.
                    </DialogDescription>
                  </DialogHeader>
                  <div className="space-y-4 mt-2">
                    <div className="space-y-2">
                      <Label>نقش هدف *</Label>
                      <Select value={codeRole} onValueChange={(v) => setCodeRole(v as OrgRole)}>
                        <SelectTrigger className="rounded-xl">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {ROLE_OPTIONS.map((r) => (
                            <SelectItem key={r.value} value={r.value}>
                              {r.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label>عنوان</Label>
                      <Input
                        value={codeLabel}
                        onChange={(e) => setCodeLabel(e.target.value)}
                        placeholder="مثلاً: کد کلاس ۱۰/الف"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>حداکثر استفاده</Label>
                      <Input
                        type="number"
                        value={codeMaxUses}
                        onChange={(e) => setCodeMaxUses(e.target.value)}
                        min={1}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>کد سفارشی (اختیاری)</Label>
                      <Input
                        value={codeCustom}
                        onChange={(e) => setCodeCustom(e.target.value.toUpperCase())}
                        placeholder="مثلاً: SCHOOL2026"
                        dir="ltr"
                        className="text-left font-mono"
                      />
                    </div>
                    <DialogFooter>
                      <Button
                        className="w-full rounded-xl"
                        onClick={handleCreateCode}
                        disabled={isSubmitting}
                      >
                        {isSubmitting ? 'در حال ایجاد...' : 'ایجاد کد'}
                      </Button>
                    </DialogFooter>
                  </div>
                </DialogContent>
              </Dialog>
            </div>

            {codesLoading ? (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <Skeleton key={i} className="h-16 rounded-xl" />
                ))}
              </div>
            ) : codesError ? (
              <ErrorState title="خطا" description={codesError} onRetry={reloadCodes} />
            ) : codes.length === 0 ? (
              <Card className="rounded-2xl border-dashed">
                <CardContent className="py-16 text-center">
                  <KeyRound className="w-10 h-10 text-muted-foreground mx-auto mb-3" />
                  <p className="font-medium">هنوز کد دعوتی ایجاد نشده</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    کد بسازید و لینک آن را بین اعضا پخش کنید.
                  </p>
                </CardContent>
              </Card>
            ) : (
              <div className="space-y-2">
                {codes.map((c) => {
                  const usagePercent = c.maxUses ? Math.round((c.useCount / c.maxUses) * 100) : 0;
                  return (
                    <Card key={c.id} className="rounded-xl hover:shadow-sm transition-shadow">
                      <CardContent className="p-4">
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                          {/* Left: code + meta */}
                          <div className="flex items-center gap-3 min-w-0">
                            <div className="flex items-center gap-1.5 shrink-0">
                              <code className="text-sm font-mono font-bold tracking-wider" dir="ltr">
                                {c.code}
                              </code>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-7 w-7"
                                onClick={() => copyToClipboard(c.code)}
                              >
                                <Copy className="w-3.5 h-3.5" />
                              </Button>
                            </div>
                            <Separator orientation="vertical" className="h-5 hidden sm:block" />
                            <Badge variant="secondary" className="text-[10px] shrink-0">
                              {c.targetRoleDisplay}
                            </Badge>
                            {c.label && (
                              <span className="text-xs text-muted-foreground truncate">{c.label}</span>
                            )}
                          </div>

                          {/* Right: usage + actions */}
                          <div className="flex items-center gap-3 self-end sm:self-auto">
                            <div className="flex items-center gap-2 min-w-[80px]">
                              <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
                                <div
                                  className={`h-full rounded-full transition-all ${
                                    usagePercent >= 90 ? 'bg-red-500' : 'bg-primary'
                                  }`}
                                  style={{ width: `${Math.min(usagePercent, 100)}%` }}
                                />
                              </div>
                              <span className="text-[11px] text-muted-foreground tabular-nums whitespace-nowrap">
                                {c.useCount}/{c.maxUses}
                              </span>
                            </div>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8"
                              onClick={() => handleToggleCode(c.id, c.isActive)}
                              title={c.isActive ? 'غیرفعال کردن' : 'فعال کردن'}
                            >
                              {c.isActive ? (
                                <Power className="w-4 h-4 text-emerald-500" />
                              ) : (
                                <PowerOff className="w-4 h-4 text-muted-foreground" />
                              )}
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8 text-destructive hover:text-destructive hover:bg-destructive/10"
                              onClick={() => handleDeleteCode(c.id)}
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </Button>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            )}
          </TabsContent>
        </Tabs>

        {/* ── Remove Member Dialog ── */}
        <Dialog open={!!deleteMemberTarget} onOpenChange={(open) => !open && setDeleteMemberTarget(null)}>
          <DialogContent className="sm:max-w-sm" dir="rtl">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-destructive">
                <AlertTriangle className="w-5 h-5" />
                حذف عضو
              </DialogTitle>
              <DialogDescription>
                آیا از حذف <strong>{deleteMemberTarget?.name}</strong> از سازمان اطمینان دارید؟
              </DialogDescription>
            </DialogHeader>
            <DialogFooter className="flex gap-2 sm:gap-2">
              <Button variant="outline" className="flex-1 rounded-xl" onClick={() => setDeleteMemberTarget(null)}>
                انصراف
              </Button>
              <Button
                variant="destructive"
                className="flex-1 rounded-xl"
                onClick={handleRemoveMember}
                disabled={isSubmitting}
              >
                {isSubmitting ? 'در حال حذف...' : 'حذف عضو'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </PageTransition>
  );
}
