'use client';

import { useState, useCallback } from 'react';
import { useOrgMembers, useInvitationCodes } from '@/hooks/use-organizations';
import { OrganizationService } from '@/services/organization-service';
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
  KeyRound,
  Copy,
  Trash2,
  Plus,
  Search,
  Power,
  PowerOff,
  UserCog,
  GraduationCap,
  AlertTriangle,
} from 'lucide-react';
import type { OrgRole } from '@/types';
import { StudyGroupsManager } from '@/components/organization/study-groups-manager';

const ROLE_OPTIONS = [
  { value: 'admin', label: 'مدیر سازمان' },
  { value: 'deputy', label: 'معاون' },
  { value: 'teacher', label: 'معلم' },
  { value: 'student', label: 'دانش‌آموز' },
] as const;

/**
 * Members + invitation-code management for a single organization.
 *
 * Shared by the platform-admin org detail page and the org manager's own
 * console (/org/members). All calls are org-scoped and the backend enforces
 * IsOrgAdmin, so this is safe to surface to managers (org_role admin/deputy).
 * ``onMembersChanged`` lets a parent refresh dependent data (e.g. dashboard
 * stats) when membership changes.
 */
export function OrgManagementPanel({
  orgId,
  onMembersChanged,
}: {
  orgId: number;
  onMembersChanged?: () => void;
}) {
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

  // ── Delete member / code confirmations ──
  const [deleteMemberTarget, setDeleteMemberTarget] = useState<{ id: number; name: string } | null>(null);
  const [deleteCodeTarget, setDeleteCodeTarget] = useState<{ id: number; code: string } | null>(null);

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

  const handleDeleteCode = async () => {
    if (!deleteCodeTarget) return;
    try {
      await OrganizationService.deleteInvitationCode(orgId, deleteCodeTarget.id);
      toast.success('کد حذف شد.');
      setDeleteCodeTarget(null);
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
      onMembersChanged?.();
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
      onMembersChanged?.();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا');
    }
  };

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      toast.success('کپی شد!');
    } catch {
      toast.error('کپی انجام نشد.');
    }
  };

  return (
    <>
      <Tabs defaultValue="members" dir="rtl">
        <TabsList className="rounded-xl">
          <TabsTrigger value="members" className="gap-1.5 rounded-lg">
            <UserCog className="w-4 h-4" />
            اعضا
          </TabsTrigger>
          <TabsTrigger value="codes" className="gap-1.5 rounded-lg">
            <KeyRound className="w-4 h-4" />
            کدهای دعوت
          </TabsTrigger>
          <TabsTrigger value="groups" className="gap-1.5 rounded-lg">
            <GraduationCap className="w-4 h-4" />
            گروه‌های آموزشی
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
            <Select value={roleFilter || 'all'} onValueChange={(v) => setRoleFilter(v === 'all' ? '' : v as OrgRole)}>
              <SelectTrigger className="w-[150px] rounded-xl">
                <SelectValue placeholder="همه نقش‌ها" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">همه نقش‌ها</SelectItem>
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
                            onClick={() => setDeleteCodeTarget({ id: c.id, code: c.code })}
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

        {/* ═════ Study Groups Tab ═════ */}
        <TabsContent value="groups">
          <StudyGroupsManager orgId={orgId} />
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

      {/* ── Delete Code Confirmation Dialog ── */}
      <Dialog open={!!deleteCodeTarget} onOpenChange={(open) => !open && setDeleteCodeTarget(null)}>
        <DialogContent className="sm:max-w-sm" dir="rtl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-destructive">
              <AlertTriangle className="w-5 h-5" />
              حذف کد دعوت
            </DialogTitle>
            <DialogDescription>
              آیا از حذف کد <strong className="font-mono" dir="ltr">{deleteCodeTarget?.code}</strong> اطمینان دارید؟
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="flex gap-2 sm:gap-2">
            <Button variant="outline" className="flex-1 rounded-xl" onClick={() => setDeleteCodeTarget(null)}>
              انصراف
            </Button>
            <Button
              variant="destructive"
              className="flex-1 rounded-xl"
              onClick={handleDeleteCode}
              disabled={isSubmitting}
            >
              حذف کد
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
