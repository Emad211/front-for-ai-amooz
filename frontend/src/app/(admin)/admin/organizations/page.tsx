'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useOrganizations } from '@/hooks/use-organizations';
import { OrganizationService } from '@/services/organization-service';
import { PageTransition } from '@/components/ui/page-transition';
import { ErrorState } from '@/components/shared/error-state';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { toast } from 'sonner';
import {
  Building2,
  Plus,
  Users,
  Copy,
  Trash2,
  Settings2,
  GraduationCap,
  Search,
  AlertTriangle,
} from 'lucide-react';

const STATUS_MAP: Record<
  string,
  { label: string; className: string }
> = {
  active: {
    label: 'فعال',
    className: 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border-emerald-500/20',
  },
  expired: {
    label: 'منقضی',
    className: 'bg-amber-500/15 text-amber-700 dark:text-amber-400 border-amber-500/20',
  },
  suspended: {
    label: 'معلق',
    className: 'bg-red-500/15 text-red-700 dark:text-red-400 border-red-500/20',
  },
};

export default function OrganizationsPage() {
  const router = useRouter();
  const { organizations, isLoading, error, reload } = useOrganizations();
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<{ id: number; name: string } | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  // ── Create Form ──
  const [formName, setFormName] = useState('');
  const [formSlug, setFormSlug] = useState('');
  const [formCapacity, setFormCapacity] = useState('50');
  const [formDescription, setFormDescription] = useState('');
  const [formPhone, setFormPhone] = useState('');
  const [formAddress, setFormAddress] = useState('');
  const [createdCode, setCreatedCode] = useState<string | null>(null);

  const resetForm = () => {
    setFormName('');
    setFormSlug('');
    setFormCapacity('50');
    setFormDescription('');
    setFormPhone('');
    setFormAddress('');
    setCreatedCode(null);
  };

  const handleCreate = async () => {
    if (!formName.trim() || !formSlug.trim()) {
      toast.error('نام و شناسه سازمان الزامی است.');
      return;
    }
    try {
      setIsSubmitting(true);
      const created = await OrganizationService.createOrganization({
        name: formName.trim(),
        slug: formSlug.trim(),
        student_capacity: parseInt(formCapacity) || 50,
        description: formDescription.trim(),
        phone: formPhone.trim(),
        address: formAddress.trim(),
      });
      toast.success(`سازمان «${created.name}» با موفقیت ایجاد شد.`);
      if (created.adminActivationCode) {
        setCreatedCode(created.adminActivationCode);
      } else {
        setIsCreateOpen(false);
        resetForm();
      }
      reload();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در ایجاد سازمان');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      setIsSubmitting(true);
      await OrganizationService.deleteOrganization(deleteTarget.id);
      toast.success(`سازمان «${deleteTarget.name}» حذف شد.`);
      setDeleteTarget(null);
      reload();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در حذف سازمان');
    } finally {
      setIsSubmitting(false);
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

  const filteredOrgs = organizations.filter(
    (org) => {
      const matchesSearch =
        !searchQuery.trim() ||
        org.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        org.slug.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesStatus = !statusFilter || org.subscriptionStatus === statusFilter;
      return matchesSearch && matchesStatus;
    },
  );

  // ── Loading ──
  if (isLoading) {
    return (
      <PageTransition>
        <div className="space-y-8">
          <div className="flex justify-between">
            <div className="space-y-2">
              <Skeleton className="h-10 w-64" />
              <Skeleton className="h-4 w-48" />
            </div>
            <Skeleton className="h-10 w-36" />
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[1, 2, 3, 4].map((i) => (
              <Skeleton key={i} className="h-24 rounded-2xl" />
            ))}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-56 rounded-2xl" />
            ))}
          </div>
        </div>
      </PageTransition>
    );
  }

  if (error) {
    return (
      <PageTransition>
        <div className="flex items-center justify-center h-[60vh] px-4">
          <div className="w-full max-w-2xl">
            <ErrorState title="خطا در دریافت سازمان‌ها" description={error} onRetry={reload} />
          </div>
        </div>
      </PageTransition>
    );
  }

  const activeCount = organizations.filter((o) => o.subscriptionStatus === 'active').length;
  const totalStudents = organizations.reduce((sum, o) => sum + (o.currentStudentCount ?? 0), 0);
  const totalCapacity = organizations.reduce((sum, o) => sum + (o.studentCapacity ?? 0), 0);

  return (
    <PageTransition>
      <div className="space-y-8">
        {/* ── Header ── */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl md:text-3xl font-black text-foreground">مدیریت سازمان‌ها</h1>
            <p className="text-muted-foreground text-sm mt-1">
              ایجاد و مدیریت مدارس، آموزشگاه‌ها و مؤسسات آموزشی
            </p>
          </div>
          <Dialog
            open={isCreateOpen}
            onOpenChange={(open) => {
              setIsCreateOpen(open);
              if (!open) resetForm();
            }}
          >
            <DialogTrigger asChild>
              <Button className="gap-2 rounded-xl">
                <Plus className="w-4 h-4" />
                سازمان جدید
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-lg" dir="rtl">
              {createdCode ? (
                <>
                  <DialogHeader>
                    <DialogTitle>سازمان ایجاد شد!</DialogTitle>
                    <DialogDescription>
                      کد فعالسازی مدیر را کپی کرده و به مدیر سازمان ارسال کنید.
                    </DialogDescription>
                  </DialogHeader>
                  <div className="mt-4 space-y-4">
                    <div className="flex items-center gap-2 bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/20 rounded-xl px-4 py-3">
                      <code
                        className="flex-1 text-lg font-mono font-bold text-emerald-700 dark:text-emerald-400 tracking-widest"
                        dir="ltr"
                      >
                        {createdCode}
                      </code>
                      <Button variant="ghost" size="icon" onClick={() => copyToClipboard(createdCode)}>
                        <Copy className="w-4 h-4" />
                      </Button>
                    </div>
                    <p className="text-xs text-muted-foreground text-center">
                      این کد یکبار مصرف است. مدیر با استفاده از آن وارد سازمان خواهد شد.
                    </p>
                    <DialogFooter>
                      <Button
                        className="w-full rounded-xl"
                        onClick={() => {
                          setIsCreateOpen(false);
                          resetForm();
                        }}
                      >
                        متوجه شدم
                      </Button>
                    </DialogFooter>
                  </div>
                </>
              ) : (
                <>
                  <DialogHeader>
                    <DialogTitle>ایجاد سازمان جدید</DialogTitle>
                    <DialogDescription>
                      اطلاعات سازمان را وارد کنید. پس از ایجاد، کد فعالسازی مدیر ساخته خواهد شد.
                    </DialogDescription>
                  </DialogHeader>
                  <div className="space-y-4 mt-2">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>نام سازمان *</Label>
                        <Input
                          value={formName}
                          onChange={(e) => setFormName(e.target.value)}
                          placeholder="دبیرستان البرز"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>شناسه (slug) *</Label>
                        <Input
                          value={formSlug}
                          onChange={(e) =>
                            setFormSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ''))
                          }
                          placeholder="alborz-high"
                          dir="ltr"
                          className="text-left font-mono"
                        />
                      </div>
                    </div>
                    <div className="space-y-2">
                      <Label>ظرفیت دانش‌آموز</Label>
                      <Input
                        type="number"
                        value={formCapacity}
                        onChange={(e) => setFormCapacity(e.target.value)}
                        min={1}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>توضیحات</Label>
                      <Textarea
                        value={formDescription}
                        onChange={(e) => setFormDescription(e.target.value)}
                        placeholder="توضیحات مختصر درباره سازمان"
                        rows={2}
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>تلفن</Label>
                        <Input
                          value={formPhone}
                          onChange={(e) => setFormPhone(e.target.value)}
                          dir="ltr"
                          className="text-left"
                          placeholder="021-12345678"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>آدرس</Label>
                        <Input
                          value={formAddress}
                          onChange={(e) => setFormAddress(e.target.value)}
                          placeholder="تهران، خیابان..."
                        />
                      </div>
                    </div>
                    <DialogFooter>
                      <Button
                        className="w-full rounded-xl"
                        onClick={handleCreate}
                        disabled={isSubmitting || !formName.trim() || !formSlug.trim()}
                      >
                        {isSubmitting ? 'در حال ایجاد...' : 'ایجاد سازمان'}
                      </Button>
                    </DialogFooter>
                  </div>
                </>
              )}
            </DialogContent>
          </Dialog>
        </div>

        {/* ── Summary Stats ── */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card className="rounded-2xl">
            <CardContent className="p-4 flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center shrink-0">
                <Building2 className="w-5 h-5 text-blue-600 dark:text-blue-400" />
              </div>
              <div>
                <p className="text-2xl font-black">{organizations.length}</p>
                <p className="text-xs text-muted-foreground">کل سازمان‌ها</p>
              </div>
            </CardContent>
          </Card>
          <Card className="rounded-2xl">
            <CardContent className="p-4 flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-emerald-500/10 flex items-center justify-center shrink-0">
                <Building2 className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
              </div>
              <div>
                <p className="text-2xl font-black">{activeCount}</p>
                <p className="text-xs text-muted-foreground">فعال</p>
              </div>
            </CardContent>
          </Card>
          <Card className="rounded-2xl">
            <CardContent className="p-4 flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-violet-500/10 flex items-center justify-center shrink-0">
                <GraduationCap className="w-5 h-5 text-violet-600 dark:text-violet-400" />
              </div>
              <div>
                <p className="text-2xl font-black">{totalStudents}</p>
                <p className="text-xs text-muted-foreground">دانش‌آموز فعال</p>
              </div>
            </CardContent>
          </Card>
          <Card className="rounded-2xl">
            <CardContent className="p-4 flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-amber-500/10 flex items-center justify-center shrink-0">
                <Users className="w-5 h-5 text-amber-600 dark:text-amber-400" />
              </div>
              <div>
                <p className="text-2xl font-black">{totalCapacity}</p>
                <p className="text-xs text-muted-foreground">ظرفیت کل</p>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* ── Search & Filter ── */}
        {organizations.length > 0 && (
          <div className="flex flex-wrap items-center gap-3">
            <div className="relative max-w-sm flex-1 min-w-[200px]">
              <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="جستجوی سازمان..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pr-9 rounded-xl"
              />
            </div>
            <div className="flex items-center gap-1.5">
              {[
                { value: '', label: 'همه' },
                { value: 'active', label: 'فعال' },
                { value: 'expired', label: 'منقضی' },
                { value: 'suspended', label: 'معلق' },
              ].map((opt) => (
                <Button
                  key={opt.value}
                  variant={statusFilter === opt.value ? 'default' : 'outline'}
                  size="sm"
                  className="h-8 rounded-lg text-xs"
                  onClick={() => setStatusFilter(opt.value)}
                >
                  {opt.label}
                </Button>
              ))}
            </div>
          </div>
        )}

        {/* ── Grid ── */}
        {filteredOrgs.length === 0 && !searchQuery ? (
          <Card className="rounded-2xl border-dashed">
            <CardContent className="flex flex-col items-center justify-center py-20 text-center">
              <div className="w-16 h-16 rounded-2xl bg-muted flex items-center justify-center mb-4">
                <Building2 className="w-8 h-8 text-muted-foreground" />
              </div>
              <h3 className="text-lg font-bold">هنوز سازمانی ایجاد نشده</h3>
              <p className="text-muted-foreground text-sm mt-1 max-w-xs">
                با کلیک روی دکمه «سازمان جدید» اولین مدرسه یا آموزشگاه را ثبت کنید.
              </p>
            </CardContent>
          </Card>
        ) : filteredOrgs.length === 0 ? (
          <Card className="rounded-2xl">
            <CardContent className="py-12 text-center text-muted-foreground">
              نتیجه‌ای برای «{searchQuery}» یافت نشد.
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {filteredOrgs.map((org) => {
              const statusInfo = STATUS_MAP[org.subscriptionStatus] ?? STATUS_MAP.active;
              const capacityPercent = org.studentCapacity
                ? Math.round(((org.currentStudentCount ?? 0) / org.studentCapacity) * 100)
                : 0;

              return (
                <Card
                  key={org.id}
                  className="rounded-2xl hover:shadow-lg transition-all duration-200 group cursor-pointer"
                  onClick={() => router.push(`/admin/organizations/${org.id}`)}
                >
                  <CardHeader className="pb-3">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-3 min-w-0">
                        {org.logo ? (
                          <img
                            src={org.logo}
                            alt={org.name}
                            className="w-11 h-11 rounded-xl object-cover shrink-0 ring-1 ring-border"
                          />
                        ) : (
                          <div className="w-11 h-11 rounded-xl bg-primary/10 flex items-center justify-center shrink-0">
                            <Building2 className="w-5 h-5 text-primary" />
                          </div>
                        )}
                        <div className="min-w-0">
                          <CardTitle className="text-base truncate">{org.name}</CardTitle>
                          <p className="text-xs text-muted-foreground font-mono mt-0.5" dir="ltr">
                            {org.slug}
                          </p>
                        </div>
                      </div>
                      <Badge className={`shrink-0 text-[10px] border ${statusInfo.className}`}>
                        {statusInfo.label}
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-3 pt-0">
                    {/* Capacity Bar */}
                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-muted-foreground flex items-center gap-1">
                          <GraduationCap className="w-3.5 h-3.5" />
                          ظرفیت
                        </span>
                        <span className="font-bold tabular-nums">
                          {org.currentStudentCount ?? 0}
                          <span className="text-muted-foreground font-normal">/{org.studentCapacity}</span>
                        </span>
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
                    </div>

                    {org.ownerName && (
                      <p className="text-xs text-muted-foreground">
                        مدیر: <span className="text-foreground font-medium">{org.ownerName}</span>
                      </p>
                    )}

                    {org.description && (
                      <p className="text-xs text-muted-foreground line-clamp-2">{org.description}</p>
                    )}

                    <Separator />

                    <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                      <Button
                        variant="outline"
                        size="sm"
                        className="flex-1 rounded-lg gap-1.5 text-xs h-8"
                        onClick={() => router.push(`/admin/organizations/${org.id}`)}
                      >
                        <Settings2 className="w-3.5 h-3.5" />
                        مدیریت
                      </Button>
                      <Button
                        variant="outline"
                        size="icon"
                        className="rounded-lg h-8 w-8 text-destructive hover:text-destructive hover:bg-destructive/10"
                        onClick={() => setDeleteTarget({ id: org.id, name: org.name })}
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}

        {/* ── Delete Dialog ── */}
        <Dialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
          <DialogContent className="sm:max-w-sm" dir="rtl">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-destructive">
                <AlertTriangle className="w-5 h-5" />
                حذف سازمان
              </DialogTitle>
              <DialogDescription>
                آیا از حذف <strong>{deleteTarget?.name}</strong> اطمینان دارید؟ تمام اعضا، کلاس‌ها و
                کدهای دعوت مرتبط نیز حذف خواهند شد.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter className="flex gap-2 sm:gap-2">
              <Button variant="outline" className="flex-1 rounded-xl" onClick={() => setDeleteTarget(null)}>
                انصراف
              </Button>
              <Button
                variant="destructive"
                className="flex-1 rounded-xl"
                onClick={handleDelete}
                disabled={isSubmitting}
              >
                {isSubmitting ? 'در حال حذف...' : 'حذف سازمان'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </PageTransition>
  );
}
