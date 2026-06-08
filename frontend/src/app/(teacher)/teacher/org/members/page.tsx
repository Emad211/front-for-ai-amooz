'use client';

import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import {
  Users,
  Ticket,
  Plus,
  Trash2,
  Copy,
  Search,
  ShieldCheck,
  Power,
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
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogTrigger,
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
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import type { OrgMembership, OrgRole, InvitationCode } from '@/types';

const ROLE_LABELS: Record<OrgRole, string> = {
  admin: 'مدیر',
  deputy: 'معاون',
  teacher: 'معلم',
  student: 'دانش‌آموز',
};

const ROLE_OPTIONS: OrgRole[] = ['admin', 'deputy', 'teacher', 'student'];

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

  // ---- Members tab state ----
  const [members, setMembers] = useState<OrgMembership[]>([]);
  const [membersLoading, setMembersLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState<'all' | OrgRole>('all');

  // ---- Codes tab state ----
  const [codes, setCodes] = useState<InvitationCode[]>([]);
  const [codesLoading, setCodesLoading] = useState(true);

  // Create-code dialog state
  const [createOpen, setCreateOpen] = useState(false);
  const [newRole, setNewRole] = useState<OrgRole>('student');
  const [newLabel, setNewLabel] = useState('');
  const [newMaxUses, setNewMaxUses] = useState('1');
  const [newExpires, setNewExpires] = useState('');
  const [creating, setCreating] = useState(false);

  async function loadMembers() {
    if (!orgId) return;
    setMembersLoading(true);
    try {
      const data = await OrganizationService.getMembers(orgId, {
        role: roleFilter === 'all' ? undefined : roleFilter,
        search: search.trim() || undefined,
      });
      setMembers(data);
    } catch {
      toast.error('بارگذاری اعضا با خطا مواجه شد.');
    } finally {
      setMembersLoading(false);
    }
  }

  async function loadCodes() {
    if (!orgId) return;
    setCodesLoading(true);
    try {
      const data = await OrganizationService.getInvitationCodes(orgId);
      setCodes(data);
    } catch {
      toast.error('بارگذاری کدهای دعوت با خطا مواجه شد.');
    } finally {
      setCodesLoading(false);
    }
  }

  // Initial load (members + codes)
  useEffect(() => {
    if (orgId) {
      loadMembers();
      loadCodes();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orgId]);

  // Re-fetch members on role-filter change.
  useEffect(() => {
    if (orgId) loadMembers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [roleFilter]);

  // Debounced search re-fetch (~300ms).
  useEffect(() => {
    if (!orgId) return;
    const t = setTimeout(() => {
      loadMembers();
    }, 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  async function handleRoleChange(member: OrgMembership, value: OrgRole) {
    if (!orgId || value === member.orgRole) return;
    try {
      await OrganizationService.updateMember(orgId, member.id, { org_role: value });
      toast.success('نقش عضو به‌روزرسانی شد.');
      loadMembers();
    } catch {
      toast.error('تغییر نقش عضو با خطا مواجه شد.');
    }
  }

  async function handleRemoveMember(member: OrgMembership) {
    if (!orgId) return;
    try {
      await OrganizationService.removeMember(orgId, member.id);
      toast.success('عضو حذف شد.');
      loadMembers();
    } catch {
      toast.error('حذف عضو با خطا مواجه شد.');
    }
  }

  async function handleCreateCode() {
    if (!orgId) return;
    const maxUses = Number(newMaxUses);
    setCreating(true);
    try {
      await OrganizationService.createInvitationCode(orgId, {
        target_role: newRole,
        label: newLabel.trim() || undefined,
        max_uses: Number.isFinite(maxUses) && maxUses > 0 ? maxUses : 1,
        expires_at: newExpires ? new Date(newExpires).toISOString() : null,
      });
      toast.success('کد دعوت ساخته شد.');
      setCreateOpen(false);
      setNewRole('student');
      setNewLabel('');
      setNewMaxUses('1');
      setNewExpires('');
      loadCodes();
    } catch {
      toast.error('ساخت کد دعوت با خطا مواجه شد.');
    } finally {
      setCreating(false);
    }
  }

  async function handleToggleCode(code: InvitationCode) {
    if (!orgId) return;
    try {
      await OrganizationService.updateInvitationCode(orgId, code.id, {
        is_active: !code.isActive,
      });
      toast.success(code.isActive ? 'کد غیرفعال شد.' : 'کد فعال شد.');
      loadCodes();
    } catch {
      toast.error('تغییر وضعیت کد با خطا مواجه شد.');
    }
  }

  async function handleDeleteCode(code: InvitationCode) {
    if (!orgId) return;
    try {
      await OrganizationService.deleteInvitationCode(orgId, code.id);
      toast.success('کد دعوت حذف شد.');
      loadCodes();
    } catch {
      toast.error('حذف کد دعوت با خطا مواجه شد.');
    }
  }

  async function handleCopyCode(code: string) {
    try {
      await navigator.clipboard.writeText(code);
      toast.success('کپی شد');
    } catch {
      toast.error('کپی کد با خطا مواجه شد.');
    }
  }

  if (!orgId) return null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">اعضا و کدهای دعوت</h1>
        <p className="text-sm text-muted-foreground mt-1">
          مدیریت اعضای سازمان، نقش‌ها و کدهای دعوت برای پیوستن کاربران جدید.
        </p>
      </div>

      <Tabs defaultValue="members" className="space-y-4">
        <TabsList>
          <TabsTrigger value="members" className="gap-2">
            <Users className="h-4 w-4" />
            اعضا
          </TabsTrigger>
          <TabsTrigger value="codes" className="gap-2">
            <Ticket className="h-4 w-4" />
            کدهای دعوت
          </TabsTrigger>
        </TabsList>

        {/* ===================== MEMBERS ===================== */}
        <TabsContent value="members" className="space-y-4">
          <div className="flex flex-col sm:flex-row gap-3 sm:items-center">
            <div className="relative flex-1">
              <Search className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="جستجوی نام یا کد داخلی…"
                className="pr-9"
              />
            </div>
            <Select
              value={roleFilter}
              onValueChange={(v) => setRoleFilter(v as 'all' | OrgRole)}
            >
              <SelectTrigger className="w-full sm:w-48">
                <SelectValue placeholder="نقش" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">همه</SelectItem>
                {ROLE_OPTIONS.map((r) => (
                  <SelectItem key={r} value={r}>
                    {ROLE_LABELS[r]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <Card className="rounded-2xl border-border/50 shadow-sm">
            <CardContent className="p-0">
              {membersLoading ? (
                <div className="p-4 space-y-3">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <Skeleton key={i} className="h-12 rounded-xl" />
                  ))}
                </div>
              ) : members.length === 0 ? (
                <div className="flex flex-col items-center justify-center text-center gap-3 py-16">
                  <div className="h-14 w-14 rounded-2xl bg-muted flex items-center justify-center">
                    <Users className="h-7 w-7 text-muted-foreground" />
                  </div>
                  <p className="text-sm text-muted-foreground">
                    هیچ عضوی با این فیلترها یافت نشد.
                  </p>
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>نام</TableHead>
                      <TableHead>تماس</TableHead>
                      <TableHead>کد داخلی</TableHead>
                      <TableHead>نقش</TableHead>
                      <TableHead>وضعیت</TableHead>
                      <TableHead className="w-12" />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {members.map((m) => (
                      <TableRow key={m.id}>
                        <TableCell className="font-medium text-foreground">
                          {m.userName}
                        </TableCell>
                        <TableCell className="text-muted-foreground" dir="ltr">
                          <span className="block text-right">
                            {m.userEmail || toPersianDigits(m.userPhone) || '—'}
                          </span>
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {m.internalId ? toPersianDigits(m.internalId) : '—'}
                        </TableCell>
                        <TableCell>
                          <Select
                            value={m.orgRole}
                            onValueChange={(v) => handleRoleChange(m, v as OrgRole)}
                          >
                            <SelectTrigger className="w-32 h-9">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {ROLE_OPTIONS.map((r) => (
                                <SelectItem key={r} value={r}>
                                  {ROLE_LABELS[r]}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant={m.status === 'active' ? 'secondary' : 'outline'}
                          >
                            {m.statusDisplay}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <AlertDialog>
                            <AlertDialogTrigger asChild>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="text-destructive hover:text-destructive"
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </AlertDialogTrigger>
                            <AlertDialogContent>
                              <AlertDialogHeader>
                                <AlertDialogTitle>حذف عضو؟</AlertDialogTitle>
                                <AlertDialogDescription>
                                  «{m.userName}» از سازمان حذف می‌شود. این اقدام
                                  قابل بازگشت نیست.
                                </AlertDialogDescription>
                              </AlertDialogHeader>
                              <AlertDialogFooter>
                                <AlertDialogCancel>انصراف</AlertDialogCancel>
                                <AlertDialogAction
                                  onClick={() => handleRemoveMember(m)}
                                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                                >
                                  حذف
                                </AlertDialogAction>
                              </AlertDialogFooter>
                            </AlertDialogContent>
                          </AlertDialog>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ===================== CODES ===================== */}
        <TabsContent value="codes" className="space-y-4">
          <div className="flex justify-end">
            <Dialog open={createOpen} onOpenChange={setCreateOpen}>
              <DialogTrigger asChild>
                <Button className="gap-2">
                  <Plus className="h-4 w-4" />
                  ایجاد کد دعوت
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>ایجاد کد دعوت</DialogTitle>
                  <DialogDescription>
                    کدی برای پیوستن کاربران جدید با نقش مشخص بسازید.
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4 py-2">
                  <div className="space-y-2">
                    <Label htmlFor="code-role">نقش هدف</Label>
                    <Select
                      value={newRole}
                      onValueChange={(v) => setNewRole(v as OrgRole)}
                    >
                      <SelectTrigger id="code-role">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {ROLE_OPTIONS.map((r) => (
                          <SelectItem key={r} value={r}>
                            {ROLE_LABELS[r]}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="code-label">برچسب (اختیاری)</Label>
                    <Input
                      id="code-label"
                      value={newLabel}
                      onChange={(e) => setNewLabel(e.target.value)}
                      placeholder="مثلاً: ورودی پاییز"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="code-max">حداکثر دفعات استفاده</Label>
                    <Input
                      id="code-max"
                      type="number"
                      min={1}
                      value={newMaxUses}
                      onChange={(e) => setNewMaxUses(e.target.value)}
                      dir="ltr"
                      className="text-right"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="code-expires">تاریخ انقضا (اختیاری)</Label>
                    <Input
                      id="code-expires"
                      type="date"
                      value={newExpires}
                      onChange={(e) => setNewExpires(e.target.value)}
                      dir="ltr"
                      className="text-right"
                    />
                  </div>
                </div>
                <DialogFooter>
                  <DialogClose asChild>
                    <Button variant="outline">انصراف</Button>
                  </DialogClose>
                  <Button onClick={handleCreateCode} disabled={creating}>
                    {creating ? 'در حال ساخت…' : 'ساخت کد'}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>

          {codesLoading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-28 rounded-2xl" />
              ))}
            </div>
          ) : codes.length === 0 ? (
            <Card className="rounded-2xl border-border/50 shadow-sm">
              <CardContent className="flex flex-col items-center justify-center text-center gap-3 py-16">
                <div className="h-14 w-14 rounded-2xl bg-muted flex items-center justify-center">
                  <Ticket className="h-7 w-7 text-muted-foreground" />
                </div>
                <p className="text-sm text-muted-foreground">
                  هنوز کد دعوتی ساخته نشده است.
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {codes.map((c) => (
                <Card
                  key={c.id}
                  className="rounded-2xl border-border/50 shadow-sm"
                >
                  <CardHeader className="pb-3">
                    <div className="flex items-center justify-between gap-2">
                      <CardTitle className="flex items-center gap-2 text-base">
                        <code
                          dir="ltr"
                          className="font-mono text-sm bg-muted px-2 py-1 rounded-lg"
                        >
                          {c.code}
                        </code>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7"
                          onClick={() => handleCopyCode(c.code)}
                        >
                          <Copy className="h-3.5 w-3.5" />
                        </Button>
                      </CardTitle>
                      <Badge
                        variant="secondary"
                        className="gap-1 whitespace-nowrap"
                      >
                        <ShieldCheck className="h-3 w-3" />
                        {c.targetRoleDisplay}
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {c.label && (
                      <p className="text-sm text-foreground">{c.label}</p>
                    )}
                    <div className="flex items-center justify-between text-sm text-muted-foreground">
                      <span>استفاده‌شده</span>
                      <span className="font-medium text-foreground">
                        {formatPersianNumber(c.useCount)}/
                        {formatPersianNumber(c.maxUses)}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-sm text-muted-foreground">
                      <span>وضعیت</span>
                      <Badge variant={c.isValid ? 'secondary' : 'outline'}>
                        {c.isValid ? 'معتبر' : 'نامعتبر'}
                      </Badge>
                    </div>
                    {c.expiresAt && (
                      <div className="flex items-center justify-between text-sm text-muted-foreground">
                        <span>انقضا</span>
                        <span className="text-foreground">
                          {formatPersianDate(c.expiresAt)}
                        </span>
                      </div>
                    )}
                    <div className="flex items-center justify-between gap-2 pt-1">
                      <Button
                        variant={c.isActive ? 'outline' : 'default'}
                        size="sm"
                        className="gap-2"
                        onClick={() => handleToggleCode(c)}
                      >
                        <Power className="h-3.5 w-3.5" />
                        {c.isActive ? 'غیرفعال‌سازی' : 'فعال‌سازی'}
                      </Button>
                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="text-destructive hover:text-destructive"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>حذف کد دعوت؟</AlertDialogTitle>
                            <AlertDialogDescription>
                              این کد دیگر قابل استفاده نخواهد بود. این اقدام قابل
                              بازگشت نیست.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>انصراف</AlertDialogCancel>
                            <AlertDialogAction
                              onClick={() => handleDeleteCode(c)}
                              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                            >
                              حذف
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
