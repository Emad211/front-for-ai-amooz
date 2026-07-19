'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { toast } from 'sonner';
import {
  KeyRound,
  Loader2,
  ArrowRight,
  Building2,
  GraduationCap,
  BookOpen,
  ShieldCheck,
  UserCog,
  Info,
} from 'lucide-react';
import { OrganizationService } from '@/services/organization-service';
import {
  inviteLogin,
  persistTokens,
  persistUser,
  fetchMe,
  type AuthMeResponse,
} from '@/services/auth-service';
import { WORKSPACE_STORAGE_KEY } from '@/hooks/use-workspace';
import type { ValidateCodeResult } from '@/types';
import { isValidIranPhone, normalizeIranPhone, sanitizeIranPhoneInput } from '@/lib/iran-phone';

/**
 * Unified "join / sign-in with a code" form.
 *
 * One entry point for BOTH code systems so a student never has to guess which
 * page to use. Redemption is now UNIFORM and phone-based for every role: the
 * code + phone create (or re-enter) a passwordless account shell, then the user
 * is sent to /onboarding to set the username/password/email they'll log in with
 * from then on. Only an already-onboarded user skips straight to their dashboard.
 *
 *  - **Org invite code** (e.g. SCHOOL2026): detected via validate-code → phone.
 *  - **Class invite code** (teacher → student): phone + code.
 */

type Step = 'code' | 'org-phone' | 'class' | 'redirecting';

const ROLE_INFO: Record<string, { label: string; icon: typeof ShieldCheck; color: string }> = {
  admin: { label: 'مدیر سازمان آموزشی', icon: ShieldCheck, color: 'text-red-500' },
  deputy: { label: 'معاون', icon: UserCog, color: 'text-orange-500' },
  teacher: { label: 'معلم', icon: BookOpen, color: 'text-blue-500' },
  student: { label: 'دانش‌آموز', icon: GraduationCap, color: 'text-emerald-500' },
};

export function UnifiedCodeForm() {
  const router = useRouter();

  const [step, setStep] = useState<Step>('code');
  const [busy, setBusy] = useState(false);

  // Code
  const [code, setCode] = useState('');
  const [codeInfo, setCodeInfo] = useState<ValidateCodeResult | null>(null);

  // Shared
  const [phone, setPhone] = useState('');
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');

  // ── Where a code-redeemer lands: onboarding first, else their dashboard. ──
  const goToDashboardForOrg = (orgRole: string, slug: string) => {
    if (orgRole === 'admin' || orgRole === 'deputy') {
      // A manager is NOT a teacher — pre-select their org workspace + open /org.
      try { localStorage.setItem(WORKSPACE_STORAGE_KEY, slug); } catch { /* ignore */ }
      router.push('/org');
    } else if (orgRole === 'teacher') {
      router.push('/teacher');
    } else {
      router.push('/home');
    }
  };

  const finishOrg = (completed: boolean, orgRole: string, slug: string) => {
    setStep('redirecting');
    if (!completed) { router.push('/onboarding'); return; }
    goToDashboardForOrg(orgRole, slug);
  };

  // Persist tokens returned by an org redeem, then hydrate + return the profile.
  const persistOrgSession = async (access?: string, refresh?: string): Promise<AuthMeResponse | null> => {
    if (!access) return null;
    persistTokens({ access, refresh: refresh ?? '' });
    try {
      const me = await fetchMe();
      persistUser(me);
      return me;
    } catch {
      return null;
    }
  };

  // ── Step 1: validate the code, then branch ──
  const handleCheckCode = async () => {
    const trimmed = code.trim();
    if (!trimmed) {
      toast.error('لطفاً کد را وارد کنید.');
      return;
    }
    setBusy(true);
    try {
      const result = await OrganizationService.validateCode(trimmed);

      if (result.valid) {
        setCodeInfo(result);
        // Already authenticated → redeem straight away (no phone needed).
        if (result.needsRegistration === false) {
          await redeemOrgAuthenticated(trimmed);
          return;
        }
        // Every role now goes through the same phone step.
        setStep('org-phone');
        return;
      }

      // Not a valid org code. If an org code with this value EXISTS (expired /
      // inactive), surface that; otherwise treat it as a class invite code.
      if (result.exists) {
        toast.error(result.detail || 'این کد دیگر معتبر نیست.');
        return;
      }
      setStep('class');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در بررسی کد');
    } finally {
      setBusy(false);
    }
  };

  // ── Org redeem (already-authenticated user joining another org) ──
  const redeemOrgAuthenticated = async (codeValue: string) => {
    setBusy(true);
    try {
      const res = await OrganizationService.redeemCode({ code: codeValue });
      toast.success(`به ${res.organization.name} خوش آمدید!`);
      let me: AuthMeResponse | null = null;
      try { me = await fetchMe(); persistUser(me); } catch { /* keep cached */ }
      finishOrg(me?.is_profile_completed ?? true, res.membership.orgRole, res.organization.slug);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در عضویت');
    } finally {
      setBusy(false);
    }
  };

  // ── Org redeem (anonymous): phone is the identity → passwordless shell. ──
  const handleOrgPhone = async () => {
    const normalized = normalizeIranPhone(phone);
    if (!isValidIranPhone(normalized)) {
      toast.error('شماره موبایل معتبر نیست.');
      return;
    }
    setBusy(true);
    try {
      const res = await OrganizationService.redeemCode({
        code: code.trim(),
        phone: normalized,
        first_name: firstName.trim(),
        last_name: lastName.trim(),
      });
      const me = await persistOrgSession(res.access, res.refresh);
      toast.success(`به ${res.organization.name} خوش آمدید!`);
      finishOrg(me?.is_profile_completed ?? false, res.membership.orgRole, res.organization.slug);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در ورود');
    } finally {
      setBusy(false);
    }
  };

  // ── Class invite: phone + code, passwordless shell. ──
  const handleClass = async () => {
    const normalized = normalizeIranPhone(phone);
    if (!isValidIranPhone(normalized)) {
      toast.error('شماره موبایل معتبر نیست.');
      return;
    }
    setBusy(true);
    try {
      const resp = await inviteLogin({ code: code.trim(), phone: normalized });
      persistTokens(resp.tokens);
      persistUser(resp.user);
      setStep('redirecting');
      router.push(resp.user.is_profile_completed ? '/home' : '/onboarding');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'کد دعوت یا شماره تماس معتبر نیست.');
    } finally {
      setBusy(false);
    }
  };

  const resetToCode = () => {
    setStep('code');
    setCodeInfo(null);
    setPhone('');
    setFirstName('');
    setLastName('');
  };

  const roleInfo = codeInfo?.targetRole ? ROLE_INFO[codeInfo.targetRole] : null;

  // ── Organization banner (shown on the org phone step) ──
  const orgBanner = codeInfo?.organization && (
    <div className="rounded-xl bg-primary/5 border border-primary/10 p-4">
      <div className="flex items-center gap-3">
        {codeInfo.organization.logo ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={codeInfo.organization.logo}
            alt={codeInfo.organization.name}
            className="w-12 h-12 rounded-xl object-cover ring-1 ring-border"
          />
        ) : (
          <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center">
            <Building2 className="w-6 h-6 text-primary" />
          </div>
        )}
        <div>
          <p className="font-bold text-foreground">{codeInfo.organization.name}</p>
          {roleInfo && (
            <Badge variant="outline" className="text-xs gap-1 mt-1">
              <roleInfo.icon className={`w-3 h-3 ${roleInfo.color}`} />
              {codeInfo.targetRoleDisplay ?? roleInfo.label}
            </Badge>
          )}
        </div>
      </div>
    </div>
  );

  return (
    <div className="w-full">
      <div className="text-center mb-6">
        <div className="w-14 h-14 rounded-2xl bg-primary/10 flex items-center justify-center mx-auto mb-4">
          <KeyRound className="w-7 h-7 text-primary" />
        </div>
        <h1 className="text-2xl font-black text-foreground">ورود با کد دعوت</h1>
        <p className="text-sm text-muted-foreground mt-1">
          {step === 'code' && 'کد سازمان آموزشی یا کد کلاسِ معلم خود را وارد کنید'}
          {step === 'org-phone' && 'شماره موبایل خود را وارد کنید؛ در گام بعد حساب می‌سازید'}
          {step === 'class' && 'برای ورود به کلاس، شماره موبایل خود را وارد کنید'}
          {step === 'redirecting' && 'در حال انتقال...'}
        </p>
      </div>

      {/* ── Step 1: code ── */}
      {step === 'code' && (
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="code">کد دعوت</Label>
            <div className="relative">
              <KeyRound className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                id="code"
                value={code}
                onChange={(e) => setCode(e.target.value.toUpperCase().slice(0, 64))}
                maxLength={64}
                placeholder="مثلاً: SCHOOL2026"
                dir="ltr"
                className="pr-10 h-12 text-center text-lg font-mono tracking-widest rounded-xl"
                disabled={busy}
                onKeyDown={(e) => e.key === 'Enter' && handleCheckCode()}
              />
            </div>
          </div>
          <Button className="w-full h-12 rounded-xl text-base" onClick={handleCheckCode} disabled={busy || !code.trim()}>
            {busy ? <><Loader2 className="ms-2 h-4 w-4 animate-spin" />در حال بررسی...</> : 'ادامه'}
          </Button>

          <Separator />
          <div className="rounded-lg bg-muted/40 p-4 flex gap-2">
            <Info className="h-5 w-5 text-primary shrink-0 mt-0.5" />
            <p className="text-xs text-muted-foreground leading-6">
              کد سازمان آموزشی را مدیر مدرسه/مؤسسه به شما می‌دهد و کد کلاس را معلم. هر دو را در همین‌جا وارد کنید — خودش تشخیص می‌دهد.
            </p>
          </div>
        </div>
      )}

      {/* ── Step 2: org redeem (phone, all roles) ── */}
      {step === 'org-phone' && (
        <div className="space-y-4">
          {orgBanner}
          <button type="button" onClick={resetToCode} className="flex items-center gap-1 text-sm text-muted-foreground hover:text-primary transition-colors">
            <ArrowRight className="w-4 h-4" /> تغییر کد
          </button>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-xs">نام</Label>
              <Input value={firstName} onChange={(e) => setFirstName(e.target.value)} className="rounded-xl" disabled={busy} />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">نام خانوادگی</Label>
              <Input value={lastName} onChange={(e) => setLastName(e.target.value)} className="rounded-xl" disabled={busy} />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">شماره موبایل *</Label>
            <Input
              type="tel"
              value={phone}
              onChange={(e) => setPhone(sanitizeIranPhoneInput(e.target.value))}
              maxLength={20}
              inputMode="numeric"
              placeholder="09123456789"
              dir="ltr"
              className="rounded-xl text-center text-lg tracking-widest"
              disabled={busy}
              onKeyDown={(e) => e.key === 'Enter' && handleOrgPhone()}
            />
          </div>
          <Button className="w-full h-12 rounded-xl text-base" onClick={handleOrgPhone} disabled={busy || !phone.trim()}>
            {busy ? <><Loader2 className="ms-2 h-4 w-4 animate-spin" />در حال ورود...</> : 'ادامه'}
          </Button>
        </div>
      )}

      {/* ── Step 2b: class invite (phone, passwordless) ── */}
      {step === 'class' && (
        <div className="space-y-4">
          <button type="button" onClick={resetToCode} className="flex items-center gap-1 text-sm text-muted-foreground hover:text-primary transition-colors">
            <ArrowRight className="w-4 h-4" /> تغییر کد
          </button>
          <div className="space-y-1.5">
            <Label className="text-xs">شماره موبایل *</Label>
            <Input
              type="tel"
              value={phone}
              onChange={(e) => setPhone(sanitizeIranPhoneInput(e.target.value))}
              maxLength={20}
              inputMode="numeric"
              placeholder="09123456789"
              dir="ltr"
              className="rounded-xl text-center text-lg tracking-widest"
              disabled={busy}
              onKeyDown={(e) => e.key === 'Enter' && handleClass()}
            />
          </div>
          <Button className="w-full h-12 rounded-xl text-base" onClick={handleClass} disabled={busy || !phone.trim()}>
            {busy ? <><Loader2 className="ms-2 h-4 w-4 animate-spin" />در حال ورود...</> : 'ورود به کلاس'}
          </Button>
        </div>
      )}

      {step === 'redirecting' && (
        <div className="flex items-center justify-center py-10">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
        </div>
      )}

      <p className="mt-6 text-sm text-center text-muted-foreground">
        حساب کاربری دارید؟{' '}
        <Link href="/login" className="font-semibold text-primary hover:underline">ورود</Link>
      </p>
    </div>
  );
}
