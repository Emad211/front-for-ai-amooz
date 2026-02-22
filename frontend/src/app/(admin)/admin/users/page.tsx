'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { UserService, type AdminUser, type UserUpdatePayload } from '@/services/user-service';
import { formatPersianDateTime } from '@/lib/date-utils';
import { PageTransition } from '@/components/ui/page-transition';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { toast } from 'sonner';
import {
  Users,
  Search,
  Pencil,
  Trash2,
  ShieldCheck,
  GraduationCap,
  BookOpen,
  UserCircle,
  RefreshCw,
} from 'lucide-react';

// ─── Constants ───────────────────────────────────────────────────────────

const ROLE_MAP: Record<string, { label: string; icon: typeof Users; className: string }> = {
  ADMIN: {
    label: 'ادمین',
    icon: ShieldCheck,
    className: 'bg-red-500/15 text-red-700 dark:text-red-400 border-red-500/20',
  },
  TEACHER: {
    label: 'معلم',
    icon: BookOpen,
    className: 'bg-blue-500/15 text-blue-700 dark:text-blue-400 border-blue-500/20',
  },
  STUDENT: {
    label: 'دانش‌آموز',
    icon: GraduationCap,
    className: 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border-emerald-500/20',
  },
};

const STATUS_BADGE = {
  active: {
    label: 'فعال',
    className: 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border-emerald-500/20',
  },
  inactive: {
    label: 'غیرفعال',
    className: 'bg-zinc-500/15 text-zinc-700 dark:text-zinc-400 border-zinc-500/20',
  },
};

// ─── Page Component ──────────────────────────────────────────────────────

export default function AdminUsersPage() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');

  // Edit dialog
  const [editUser, setEditUser] = useState<AdminUser | null>(null);
  const [editForm, setEditForm] = useState<UserUpdatePayload>({});
  const [saving, setSaving] = useState(false);

  // Delete dialog
  const [deleteTarget, setDeleteTarget] = useState<AdminUser | null>(null);
  const [deleting, setDeleting] = useState(false);

  // ─── Data Fetching ──────────────────────────────────────────────────────

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await UserService.getUsers();
      setUsers(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطا در دریافت کاربران');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  // ─── Filtered Users ────────────────────────────────────────────────────

  const filteredUsers = useMemo(() => {
    let result = users;

    if (search.trim()) {
      const q = search.trim().toLowerCase();
      result = result.filter(
        (u) =>
          u.username.toLowerCase().includes(q) ||
          u.fullName.toLowerCase().includes(q) ||
          (u.email ?? '').toLowerCase().includes(q) ||
          (u.phone ?? '').includes(q)
      );
    }

    if (roleFilter !== 'ALL') {
      result = result.filter((u) => u.role === roleFilter);
    }

    if (statusFilter !== 'ALL') {
      const wantActive = statusFilter === 'ACTIVE';
      result = result.filter((u) => u.isActive === wantActive);
    }

    return result;
  }, [users, search, roleFilter, statusFilter]);

  // ─── Stats ──────────────────────────────────────────────────────────────

  const stats = useMemo(() => {
    const total = users.length;
    const admins = users.filter((u) => u.role === 'ADMIN').length;
    const teachers = users.filter((u) => u.role === 'TEACHER').length;
    const students = users.filter((u) => u.role === 'STUDENT').length;
    const active = users.filter((u) => u.isActive).length;
    return { total, admins, teachers, students, active };
  }, [users]);

  // ─── Edit Handlers ─────────────────────────────────────────────────────

  const openEdit = (user: AdminUser) => {
    setEditUser(user);
    setEditForm({
      role: user.role,
      is_active: user.isActive,
      is_staff: user.isStaff,
      first_name: user.first_name,
      last_name: user.last_name,
      email: user.email,
      phone: user.phone ?? '',
    });
  };

  const handleSave = async () => {
    if (!editUser) return;
    setSaving(true);
    try {
      const updated = await UserService.updateUser(editUser.id, editForm);
      setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
      toast.success('اطلاعات کاربر با موفقیت ویرایش شد.');
      setEditUser(null);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در ویرایش کاربر');
    } finally {
      setSaving(false);
    }
  };

  // ─── Delete Handlers ───────────────────────────────────────────────────

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await UserService.deleteUser(deleteTarget.id);
      setUsers((prev) => prev.filter((u) => u.id !== deleteTarget.id));
      toast.success(`کاربر «${deleteTarget.fullName}» حذف شد.`);
      setDeleteTarget(null);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در حذف کاربر');
    } finally {
      setDeleting(false);
    }
  };

  // ─── Render ─────────────────────────────────────────────────────────────

  if (error) {
    return (
      <PageTransition>
        <div className="flex flex-col items-center justify-center py-20 gap-4">
          <p className="text-destructive text-lg">{error}</p>
          <Button onClick={fetchUsers} variant="outline">
            تلاش مجدد
          </Button>
        </div>
      </PageTransition>
    );
  }

  return (
    <PageTransition>
      <div className="space-y-6" dir="rtl">
        {/* ── Header ───────────────────────────────────────────────── */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Users className="h-6 w-6 text-primary" />
              مدیریت کاربران
            </h1>
            <p className="text-muted-foreground text-sm mt-1">
              مشاهده، ویرایش و حذف کاربران پلتفرم
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={fetchUsers} disabled={loading}>
            <RefreshCw className={`h-4 w-4 ml-2 ${loading ? 'animate-spin' : ''}`} />
            به‌روزرسانی
          </Button>
        </div>

        {/* ── Stats Cards ──────────────────────────────────────────── */}
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          {[
            { label: 'کل کاربران', value: stats.total, icon: Users },
            { label: 'ادمین‌ها', value: stats.admins, icon: ShieldCheck },
            { label: 'معلمان', value: stats.teachers, icon: BookOpen },
            { label: 'دانش‌آموزان', value: stats.students, icon: GraduationCap },
            { label: 'فعال', value: stats.active, icon: UserCircle },
          ].map((s) => (
            <Card key={s.label} className="border-border/50">
              <CardContent className="p-4 flex items-center gap-3">
                <div className="p-2 rounded-lg bg-primary/10">
                  <s.icon className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <p className="text-2xl font-bold">{loading ? '…' : s.value}</p>
                  <p className="text-xs text-muted-foreground">{s.label}</p>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* ── Filters ──────────────────────────────────────────────── */}
        <Card className="border-border/50">
          <CardContent className="p-4">
            <div className="flex flex-col sm:flex-row gap-3">
              <div className="relative flex-1">
                <Search className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="جستجو بر اساس نام، ایمیل، تلفن …"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="pr-10"
                />
              </div>
              <Select value={roleFilter} onValueChange={setRoleFilter}>
                <SelectTrigger className="w-full sm:w-[140px]">
                  <SelectValue placeholder="نقش" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="ALL">همه نقش‌ها</SelectItem>
                  <SelectItem value="ADMIN">ادمین</SelectItem>
                  <SelectItem value="TEACHER">معلم</SelectItem>
                  <SelectItem value="STUDENT">دانش‌آموز</SelectItem>
                </SelectContent>
              </Select>
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="w-full sm:w-[140px]">
                  <SelectValue placeholder="وضعیت" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="ALL">همه</SelectItem>
                  <SelectItem value="ACTIVE">فعال</SelectItem>
                  <SelectItem value="INACTIVE">غیرفعال</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>

        {/* ── Users Table ──────────────────────────────────────────── */}
        <Card className="border-border/50">
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-semibold">
              {loading ? 'در حال بارگذاری…' : `${filteredUsers.length} کاربر`}
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {loading ? (
              <div className="p-6 space-y-3">
                {Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} className="h-14 bg-muted/50 rounded-lg animate-pulse" />
                ))}
              </div>
            ) : filteredUsers.length === 0 ? (
              <div className="p-10 text-center text-muted-foreground">
                کاربری یافت نشد.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border/50 text-muted-foreground text-xs">
                      <th className="text-right px-4 py-3 font-medium">کاربر</th>
                      <th className="text-right px-4 py-3 font-medium hidden md:table-cell">ایمیل</th>
                      <th className="text-right px-4 py-3 font-medium">نقش</th>
                      <th className="text-right px-4 py-3 font-medium hidden sm:table-cell">وضعیت</th>
                      <th className="text-right px-4 py-3 font-medium hidden lg:table-cell">تاریخ عضویت</th>
                      <th className="text-right px-4 py-3 font-medium hidden lg:table-cell">آخرین ورود</th>
                      <th className="text-center px-4 py-3 font-medium">عملیات</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredUsers.map((user) => {
                      const roleMeta = ROLE_MAP[user.role] ?? ROLE_MAP.STUDENT;
                      const statusMeta = user.isActive
                        ? STATUS_BADGE.active
                        : STATUS_BADGE.inactive;

                      return (
                        <tr
                          key={user.id}
                          className="border-b border-border/30 hover:bg-muted/30 transition-colors"
                        >
                          {/* User info */}
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-3">
                              <div className="w-9 h-9 rounded-full bg-primary/10 flex items-center justify-center text-primary font-bold text-xs shrink-0">
                                {user.fullName.charAt(0).toUpperCase()}
                              </div>
                              <div className="min-w-0">
                                <p className="font-medium truncate">{user.fullName}</p>
                                <p className="text-xs text-muted-foreground truncate">
                                  @{user.username}
                                </p>
                              </div>
                            </div>
                          </td>

                          {/* Email */}
                          <td className="px-4 py-3 hidden md:table-cell text-muted-foreground">
                            {user.email || '—'}
                          </td>

                          {/* Role */}
                          <td className="px-4 py-3">
                            <Badge
                              variant="outline"
                              className={`text-xs ${roleMeta.className}`}
                            >
                              {roleMeta.label}
                            </Badge>
                          </td>

                          {/* Status */}
                          <td className="px-4 py-3 hidden sm:table-cell">
                            <Badge
                              variant="outline"
                              className={`text-xs ${statusMeta.className}`}
                            >
                              {statusMeta.label}
                            </Badge>
                          </td>

                          {/* Date Joined */}
                          <td className="px-4 py-3 hidden lg:table-cell text-xs text-muted-foreground">
                            {formatPersianDateTime(user.dateJoined)}
                          </td>

                          {/* Last Login */}
                          <td className="px-4 py-3 hidden lg:table-cell text-xs text-muted-foreground">
                            {formatPersianDateTime(user.lastLogin)}
                          </td>

                          {/* Actions */}
                          <td className="px-4 py-3">
                            <div className="flex items-center justify-center gap-1">
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8 text-muted-foreground hover:text-primary"
                                onClick={() => openEdit(user)}
                                title="ویرایش"
                              >
                                <Pencil className="h-4 w-4" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8 text-muted-foreground hover:text-destructive"
                                onClick={() => setDeleteTarget(user)}
                                title="حذف"
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>

        {/* ── Edit Dialog ──────────────────────────────────────────── */}
        <Dialog open={!!editUser} onOpenChange={(open) => !open && setEditUser(null)}>
          <DialogContent className="sm:max-w-md" dir="rtl">
            <DialogHeader>
              <DialogTitle>ویرایش کاربر</DialogTitle>
              <DialogDescription>
                {editUser ? `${editUser.fullName} (@${editUser.username})` : ''}
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4 py-2">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label>نام</Label>
                  <Input
                    value={editForm.first_name ?? ''}
                    onChange={(e) =>
                      setEditForm((f) => ({ ...f, first_name: e.target.value }))
                    }
                  />
                </div>
                <div>
                  <Label>نام خانوادگی</Label>
                  <Input
                    value={editForm.last_name ?? ''}
                    onChange={(e) =>
                      setEditForm((f) => ({ ...f, last_name: e.target.value }))
                    }
                  />
                </div>
              </div>

              <div>
                <Label>ایمیل</Label>
                <Input
                  type="email"
                  value={editForm.email ?? ''}
                  onChange={(e) =>
                    setEditForm((f) => ({ ...f, email: e.target.value }))
                  }
                />
              </div>

              <div>
                <Label>تلفن</Label>
                <Input
                  value={editForm.phone ?? ''}
                  onChange={(e) =>
                    setEditForm((f) => ({ ...f, phone: e.target.value }))
                  }
                />
              </div>

              <div>
                <Label>نقش</Label>
                <Select
                  value={editForm.role ?? 'STUDENT'}
                  onValueChange={(v) => setEditForm((f) => ({ ...f, role: v }))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="ADMIN">ادمین</SelectItem>
                    <SelectItem value="TEACHER">معلم</SelectItem>
                    <SelectItem value="STUDENT">دانش‌آموز</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <Separator />

              <div className="flex items-center justify-between">
                <Label>حساب فعال</Label>
                <Button
                  variant={editForm.is_active ? 'default' : 'outline'}
                  size="sm"
                  onClick={() =>
                    setEditForm((f) => ({ ...f, is_active: !f.is_active }))
                  }
                >
                  {editForm.is_active ? 'فعال' : 'غیرفعال'}
                </Button>
              </div>

              <div className="flex items-center justify-between">
                <Label>دسترسی Staff</Label>
                <Button
                  variant={editForm.is_staff ? 'default' : 'outline'}
                  size="sm"
                  onClick={() =>
                    setEditForm((f) => ({ ...f, is_staff: !f.is_staff }))
                  }
                >
                  {editForm.is_staff ? 'بله' : 'خیر'}
                </Button>
              </div>
            </div>

            <DialogFooter className="gap-2 sm:gap-0">
              <Button variant="outline" onClick={() => setEditUser(null)}>
                انصراف
              </Button>
              <Button onClick={handleSave} disabled={saving}>
                {saving ? 'در حال ذخیره…' : 'ذخیره تغییرات'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* ── Delete Confirmation ──────────────────────────────────── */}
        <AlertDialog
          open={!!deleteTarget}
          onOpenChange={(open) => !open && setDeleteTarget(null)}
        >
          <AlertDialogContent dir="rtl">
            <AlertDialogHeader>
              <AlertDialogTitle>
                حذف کاربر «{deleteTarget?.fullName}»
              </AlertDialogTitle>
              <AlertDialogDescription>
                آیا مطمئن هستید؟ این عملیات قابل بازگشت نیست و تمام داده‌های
                مربوط به این کاربر حذف خواهد شد.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter className="gap-2 sm:gap-0">
              <AlertDialogCancel>انصراف</AlertDialogCancel>
              <AlertDialogAction
                onClick={handleDelete}
                disabled={deleting}
                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              >
                {deleting ? 'در حال حذف…' : 'حذف کاربر'}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </PageTransition>
  );
}
