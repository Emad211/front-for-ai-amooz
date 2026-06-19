'use client';

import { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';
import {
  Building2,
  GraduationCap,
  Phone,
  Mail,
  MapPin,
  Users,
  Globe,
  Loader2,
  Check,
  X,
  Copy,
  ClipboardList,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
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
import { cn } from '@/lib/utils';
import {
  approveAccessRequest,
  listAccessRequests,
  rejectAccessRequest,
  type AccessRequestAdmin,
  type AccessRequestKind,
  type AccessRequestStatus,
} from '@/services/waitlist-service';

type StatusFilter = AccessRequestStatus | 'all';
type KindFilter = AccessRequestKind | 'all';

const STATUS_TABS: { key: StatusFilter; label: string }[] = [
  { key: 'pending', label: 'در انتظار' },
  { key: 'approved', label: 'تأیید شده' },
  { key: 'rejected', label: 'رد شده' },
  { key: 'all', label: 'همه' },
];

const KIND_TABS: { key: KindFilter; label: string }[] = [
  { key: 'all', label: 'همه' },
  { key: 'teacher', label: 'معلم' },
  { key: 'organization', label: 'سازمان آموزشی' },
];

function formatDate(value: string | null): string {
  if (!value) return '—';
  try {
    return new Date(value).toLocaleDateString('fa-IR', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  } catch {
    return value;
  }
}

function StatusBadge({ status, label }: { status: AccessRequestStatus; label: string }) {
  const styles: Record<AccessRequestStatus, string> = {
    pending: 'bg-amber-500/10 text-amber-600 border-amber-500/30',
    contacted: 'bg-blue-500/10 text-blue-600 border-blue-500/30',
    approved: 'bg-green-500/10 text-green-600 border-green-500/30',
    rejected: 'bg-destructive/10 text-destructive border-destructive/30',
  };
  return (
    <Badge variant="outline" className={cn('text-xs', styles[status])}>
      {label}
    </Badge>
  );
}

export default function AdminWaitlistPage() {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('pending');
  const [kindFilter, setKindFilter] = useState<KindFilter>('all');
  const [items, setItems] = useState<AccessRequestAdmin[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actioningId, setActioningId] = useState<number | null>(null);

  const [rejectTarget, setRejectTarget] = useState<AccessRequestAdmin | null>(null);
  const [rejectReason, setRejectReason] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listAccessRequests({
        status: statusFilter === 'all' ? undefined : statusFilter,
        kind: kindFilter === 'all' ? undefined : kindFilter,
      });
      setItems(data.results);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطا در دریافت درخواست‌ها');
    } finally {
      setLoading(false);
    }
  }, [statusFilter, kindFilter]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleApprove(item: AccessRequestAdmin) {
    setActioningId(item.id);
    try {
      const updated = await approveAccessRequest(item.id);
      setItems((prev) => prev.map((it) => (it.id === item.id ? updated : it)));
      toast.success('درخواست تأیید شد. کد/توکن ثبت‌نام آماده ارسال است.');
      if (statusFilter === 'pending') {
        // It no longer matches the pending filter — drop it after a beat.
        setItems((prev) => prev.filter((it) => it.id !== item.id));
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'تأیید ناموفق بود');
    } finally {
      setActioningId(null);
    }
  }

  async function handleReject() {
    if (!rejectTarget) return;
    setActioningId(rejectTarget.id);
    try {
      await rejectAccessRequest(rejectTarget.id, rejectReason.trim());
      setItems((prev) =>
        statusFilter === 'pending'
          ? prev.filter((it) => it.id !== rejectTarget.id)
          : prev.map((it) =>
              it.id === rejectTarget.id
                ? { ...it, status: 'rejected', reject_reason: rejectReason.trim() }
                : it
            )
      );
      toast.success('درخواست رد شد.');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'رد درخواست ناموفق بود');
    } finally {
      setActioningId(null);
      setRejectTarget(null);
      setRejectReason('');
    }
  }

  function copyToken(token: string) {
    navigator.clipboard?.writeText(token).then(
      () => toast.success('کپی شد'),
      () => toast.error('کپی نشد')
    );
  }

  return (
    <div dir="rtl" className="space-y-6">
      <div className="flex items-center gap-3">
        <div className="p-2.5 rounded-xl bg-primary/10">
          <ClipboardList className="h-6 w-6 text-primary" />
        </div>
        <div>
          <h1 className="text-2xl font-black text-foreground">درخواست‌های دسترسی</h1>
          <p className="text-sm text-muted-foreground">
            درخواست‌های همکاری معلم‌ها و سازمان‌های آموزشی را بررسی، تأیید یا رد کنید.
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex flex-wrap gap-1 rounded-xl bg-muted/40 p-1">
          {STATUS_TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setStatusFilter(t.key)}
              className={cn(
                'px-3 py-1.5 rounded-lg text-sm font-bold transition-all',
                statusFilter === t.key
                  ? 'bg-primary text-primary-foreground shadow'
                  : 'text-muted-foreground hover:text-foreground'
              )}
            >
              {t.label}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap gap-1 rounded-xl bg-muted/40 p-1">
          {KIND_TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setKindFilter(t.key)}
              className={cn(
                'px-3 py-1.5 rounded-lg text-sm font-bold transition-all',
                kindFilter === t.key
                  ? 'bg-secondary text-secondary-foreground shadow'
                  : 'text-muted-foreground hover:text-foreground'
              )}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      {loading ? (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-32 w-full rounded-2xl" />
          ))}
        </div>
      ) : error ? (
        <Card>
          <CardContent className="py-10 text-center space-y-3">
            <p className="text-sm text-destructive">{error}</p>
            <Button variant="outline" onClick={load}>
              تلاش دوباره
            </Button>
          </CardContent>
        </Card>
      ) : items.length === 0 ? (
        <Card>
          <CardContent className="py-16 text-center text-muted-foreground">
            درخواستی با این فیلتر وجود ندارد.
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {items.map((item) => {
            const isOrg = item.kind === 'organization';
            const busy = actioningId === item.id;
            const decidable = item.status === 'pending' || item.status === 'contacted';
            return (
              <Card key={item.id} className="overflow-hidden">
                <CardContent className="p-4 sm:p-5 space-y-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <div
                        className={cn(
                          'p-2.5 rounded-xl',
                          isOrg ? 'bg-indigo-500/10 text-indigo-600' : 'bg-blue-500/10 text-blue-600'
                        )}
                      >
                        {isOrg ? <Building2 className="h-5 w-5" /> : <GraduationCap className="h-5 w-5" />}
                      </div>
                      <div>
                        <p className="font-bold text-foreground">
                          {isOrg ? item.org_name : item.full_name}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {item.kind_display}
                          {isOrg && item.full_name ? ` · رابط: ${item.full_name}` : ''}
                          {' · '}
                          {formatDate(item.created_at)}
                        </p>
                      </div>
                    </div>
                    <StatusBadge status={item.status} label={item.status_display} />
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm text-muted-foreground">
                    <span className="inline-flex items-center gap-2" dir="ltr">
                      <Phone className="h-4 w-4 shrink-0" />
                      {item.phone}
                    </span>
                    {item.email && (
                      <span className="inline-flex items-center gap-2" dir="ltr">
                        <Mail className="h-4 w-4 shrink-0" />
                        {item.email}
                      </span>
                    )}
                    {!isOrg && item.expertise && (
                      <span className="inline-flex items-center gap-2">
                        <GraduationCap className="h-4 w-4 shrink-0" />
                        {item.expertise}
                      </span>
                    )}
                    {isOrg && item.city && (
                      <span className="inline-flex items-center gap-2">
                        <MapPin className="h-4 w-4 shrink-0" />
                        {item.city}
                      </span>
                    )}
                    {isOrg && item.expected_students != null && (
                      <span className="inline-flex items-center gap-2">
                        <Users className="h-4 w-4 shrink-0" />
                        {item.expected_students} دانش‌آموز
                      </span>
                    )}
                    {isOrg && item.website && (
                      <a
                        href={item.website}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-2 text-primary hover:underline"
                        dir="ltr"
                      >
                        <Globe className="h-4 w-4 shrink-0" />
                        {item.website}
                      </a>
                    )}
                  </div>

                  {item.note && (
                    <p className="text-sm text-muted-foreground bg-muted/30 rounded-lg p-3">{item.note}</p>
                  )}

                  {item.status === 'approved' && item.registration_token && (
                    <div className="rounded-lg border border-green-500/30 bg-green-500/5 p-3 space-y-2">
                      <p className="text-xs font-bold text-green-700">
                        {isOrg ? 'کد فعال‌سازی مدیر سازمان آموزشی' : 'توکن ثبت‌نام معلم'} — برای ارسال به متقاضی:
                      </p>
                      <div className="flex items-center gap-2">
                        <code className="flex-1 text-xs bg-background/60 rounded px-2 py-1.5 break-all" dir="ltr">
                          {item.registration_token}
                        </code>
                        <Button size="sm" variant="outline" onClick={() => copyToken(item.registration_token)}>
                          <Copy className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  )}

                  {item.status === 'rejected' && item.reject_reason && (
                    <p className="text-sm text-destructive bg-destructive/5 rounded-lg p-3">
                      دلیل رد: {item.reject_reason}
                    </p>
                  )}

                  {decidable && (
                    <div className="flex items-center gap-2 pt-1">
                      <Button
                        size="sm"
                        className="gap-1.5 bg-green-600 hover:bg-green-700"
                        disabled={busy}
                        onClick={() => handleApprove(item)}
                      >
                        {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
                        تأیید
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        className="gap-1.5 text-destructive hover:bg-destructive/10 hover:text-destructive"
                        disabled={busy}
                        onClick={() => {
                          setRejectTarget(item);
                          setRejectReason('');
                        }}
                      >
                        <X className="h-4 w-4" />
                        رد
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Reject dialog */}
      <AlertDialog open={!!rejectTarget} onOpenChange={(open) => !open && setRejectTarget(null)}>
        <AlertDialogContent dir="rtl">
          <AlertDialogHeader>
            <AlertDialogTitle>رد درخواست</AlertDialogTitle>
            <AlertDialogDescription>
              دلیل رد را وارد کنید (اختیاری). متقاضی می‌تواند بعداً دوباره درخواست دهد.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <textarea
            rows={3}
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            placeholder="مثلاً: مدارک ناقص است"
            className="flex w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          />
          <AlertDialogFooter>
            <AlertDialogCancel>انصراف</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleReject}
              className="bg-destructive hover:bg-destructive/90"
            >
              رد درخواست
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
