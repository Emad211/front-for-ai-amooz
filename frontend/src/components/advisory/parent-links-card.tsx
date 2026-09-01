'use client';

import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import {
  AlertCircle,
  Loader2,
  RefreshCw,
  Trash2,
  UserPlus,
} from 'lucide-react';

import {
  AdvisoryService,
  type ParentLinkOut,
} from '@/services/advisory-service';
import { toEnglishDigits, toPersianDigits } from '@/lib/persian-digits';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
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

/** Persian labels for the wire relation codes — rendered from here and by the
 * student-side my-parents-card, so the raw codes never leak into the UI. */
export const PARENT_RELATION_LABELS: Record<string, string> = {
  father: 'پدر',
  mother: 'مادر',
  guardian: 'سرپرست',
};

/** Status badge per wire status. REVOKED is declared for type-completeness but
 * never rendered — revoked rows are filtered out of the list below. */
const PARENT_STATUS_BADGE: Record<
  ParentLinkOut['status'],
  { variant: 'secondary' | 'default' | 'outline'; label: string }
> = {
  PENDING: { variant: 'secondary', label: 'در انتظار تأیید' },
  ACTIVE: { variant: 'default', label: 'فعال' },
  REVOKED: { variant: 'outline', label: 'لغو شده' },
};

/** Server-enforced cap: at most two live (PENDING+ACTIVE) parents per student. */
const MAX_LIVE_PARENTS = 2;

const PHONE_PATTERN = /^09\d{9}$/;

/** Canonicalize typed digits to ASCII (Persian-tolerant), same posture as the
 * invite form: the payload is ASCII even when the advisor typed ۰۹… */
function sanitizePhoneInput(value: string): string {
  return toEnglishDigits(value).replace(/\D/g, '').slice(0, 11);
}

/**
 * The advisor's «افزودن والد» card: lists one student's parent links, invites
 * a new parent by phone (only the masked number ever comes back), and revokes
 * an existing link behind a confirm. REVOKED rows are filtered out of the list
 * and out of the two-live-parent cap; the add form hides once that cap is hit.
 */
export function ParentLinksCard({ engagementId }: { engagementId: number }) {
  const [links, setLinks] = useState<ParentLinkOut[] | null>(null);
  const [error, setError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);

  const [phone, setPhone] = useState('');
  const [relation, setRelation] = useState('father');
  const [sending, setSending] = useState(false);

  const [pendingRevoke, setPendingRevoke] = useState<ParentLinkOut | null>(
    null,
  );
  const [revoking, setRevoking] = useState(false);

  useEffect(() => {
    let active = true;
    setError('');
    setLinks(null);
    AdvisoryService.getStudentParents(engagementId)
      .then((res) => {
        if (active) setLinks(res.links);
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : 'خطای نامشخص');
      });
    return () => {
      active = false;
    };
  }, [engagementId, reloadKey]);

  const refetch = () => {
    AdvisoryService.getStudentParents(engagementId)
      .then((res) => setLinks(res.links))
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'خطای نامشخص');
      });
  };

  const liveLinks = (links ?? []).filter(
    (link) => link.status === 'PENDING' || link.status === 'ACTIVE',
  );

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!PHONE_PATTERN.test(phone)) {
      toast.error('شماره موبایل را به شکل ۰۹۱۲۳۴۵۶۷۸۹ وارد کنید.');
      return;
    }
    setSending(true);
    try {
      await AdvisoryService.addStudentParent(engagementId, { phone, relation });
      toast.success('دعوت برای والد پیامک شد.');
      setPhone('');
      refetch();
    } catch (err: unknown) {
      // Includes the quota and bad-phone Persian details verbatim.
      toast.error(err instanceof Error ? err.message : 'ارسال دعوت ناموفق بود.');
    } finally {
      setSending(false);
    }
  };

  const handleRevoke = async () => {
    const target = pendingRevoke;
    if (!target) return;
    setRevoking(true);
    try {
      await AdvisoryService.revokeStudentParent(engagementId, target.id);
      toast.success('والد حذف شد.');
      setPendingRevoke(null);
      refetch();
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'حذف والد ناموفق بود.');
    } finally {
      setRevoking(false);
    }
  };

  const loading = links === null && !error;

  return (
    <Card dir="rtl" className="rounded-2xl border-border/50">
      <CardHeader className="p-5 pb-4">
        <CardTitle className="flex items-center gap-2 text-sm font-semibold">
          <UserPlus className="h-4 w-4 text-primary" />
          والدین دانش‌آموز
        </CardTitle>
        <CardDescription className="mt-1 text-xs leading-relaxed text-muted-foreground">
          شمارهٔ والد را ثبت کنید تا گزارش هفتگی برایش پیامک شود.
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-4 p-5 pt-0">
        {error && (
          <div
            role="alert"
            className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-destructive/40 bg-destructive/5 px-3 py-2"
          >
            <p className="flex items-center gap-2 text-xs text-destructive">
              <AlertCircle className="h-3.5 w-3.5 shrink-0" />
              {error}
            </p>
            <Button
              variant="outline"
              size="sm"
              className="h-11"
              onClick={() => setReloadKey((k) => k + 1)}
            >
              <RefreshCw className="ml-2 h-3.5 w-3.5" />
              تلاش مجدد
            </Button>
          </div>
        )}

        {loading && (
          <div className="space-y-2" aria-busy="true">
            {[0, 1].map((i) => (
              <Skeleton key={i} className="h-12 w-full rounded-xl" />
            ))}
          </div>
        )}

        {!error && !loading && (
          <div aria-live="polite" className="space-y-4">
            {liveLinks.length === 0 ? (
              <p className="text-center text-xs leading-relaxed text-muted-foreground">
                هنوز والدی ثبت نشده است.
                <br />
                شمارهٔ والد را در فرم زیر وارد کنید تا دعوت برایش پیامک شود.
              </p>
            ) : (
              <ul className="divide-y divide-border/40 rounded-xl border border-border/40">
                {liveLinks.map((link) => (
                  <li
                    key={link.id}
                    className="flex flex-wrap items-center gap-x-3 gap-y-2 px-3 py-2.5"
                  >
                    <span className="text-sm font-medium">
                      {PARENT_RELATION_LABELS[link.relation] ?? link.relation}
                    </span>
                    <span
                      dir="ltr"
                      className="text-xs tabular-nums text-muted-foreground"
                    >
                      {toPersianDigits(link.phoneMasked)}
                    </span>
                    <span className="ms-auto flex items-center gap-2">
                      <Badge
                        variant={PARENT_STATUS_BADGE[link.status].variant}
                        className="text-[11px] font-normal"
                      >
                        {PARENT_STATUS_BADGE[link.status].label}
                      </Badge>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        aria-label="حذف والد"
                        className="h-11 w-11 text-destructive hover:text-destructive"
                        disabled={pendingRevoke !== null}
                        onClick={() => setPendingRevoke(link)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </span>
                  </li>
                ))}
              </ul>
            )}

            {liveLinks.length < MAX_LIVE_PARENTS ? (
              <form
                onSubmit={handleSubmit}
                className="space-y-3 rounded-xl border border-border/40 p-4"
              >
                <p className="text-sm font-medium">افزودن والد</p>
                <div className="grid grid-cols-1 gap-x-3 gap-y-3 sm:grid-cols-[minmax(0,1fr)_auto]">
                  <div className="space-y-1.5">
                    <label
                      htmlFor="parent-phone"
                      className="text-[11px] font-medium text-muted-foreground"
                    >
                      شمارهٔ موبایل والد
                    </label>
                    <Input
                      id="parent-phone"
                      dir="ltr"
                      inputMode="numeric"
                      value={phone}
                      onChange={(e) => setPhone(sanitizePhoneInput(e.target.value))}
                      maxLength={11}
                      placeholder="۰۹۱۲۳۴۵۶۷۸۹"
                      aria-label="شمارهٔ موبایل والد"
                      className="h-11 w-full rounded-lg text-sm tabular-nums"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label
                      htmlFor="parent-relation"
                      className="text-[11px] font-medium text-muted-foreground"
                    >
                      نسبت
                    </label>
                    <Select dir="rtl" value={relation} onValueChange={setRelation}>
                      <SelectTrigger
                        id="parent-relation"
                        className="h-11 w-full rounded-lg text-sm sm:w-32"
                      >
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {Object.keys(PARENT_RELATION_LABELS).map((code) => (
                          <SelectItem key={code} value={code}>
                            {PARENT_RELATION_LABELS[code]}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="flex justify-start border-t border-border/40 pt-3">
                  <Button type="submit" className="h-11 px-5" disabled={sending}>
                    {sending && <Loader2 className="ml-2 h-4 w-4 animate-spin" />}
                    {sending ? 'در حال ارسال…' : 'ارسال دعوت'}
                  </Button>
                </div>
              </form>
            ) : (
              <p className="text-xs leading-relaxed text-muted-foreground">
                حداکثر دو والد برای هر دانش‌آموز مجاز است؛ برای افزودن والد
                جدید، ابتدا یکی از والدین فعلی را حذف کنید.
              </p>
            )}
          </div>
        )}
      </CardContent>

      <AlertDialog
        open={pendingRevoke !== null}
        onOpenChange={(open) => {
          if (!open) setPendingRevoke(null);
        }}
      >
        <AlertDialogContent dir="rtl">
          <AlertDialogHeader>
            <AlertDialogTitle>والد حذف شود؟</AlertDialogTitle>
            <AlertDialogDescription>
              دسترسی او به گزارش قطع می‌شود.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={revoking}>انصراف</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={revoking}
              onClick={(e) => {
                e.preventDefault();
                handleRevoke();
              }}
            >
              {revoking && <Loader2 className="ml-2 h-4 w-4 animate-spin" />}
              {revoking ? 'در حال انجام…' : 'حذف'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Card>
  );
}
