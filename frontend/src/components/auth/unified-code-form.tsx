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
  Lock,
  Eye,
  EyeOff,
  Info,
} from 'lucide-react';
import { OrganizationService } from '@/services/organization-service';
import {
  inviteLogin,
  persistTokens,
  persistUser,
  fetchMe,
} from '@/services/auth-service';
import { WORKSPACE_STORAGE_KEY } from '@/hooks/use-workspace';
import type { ValidateCodeResult } from '@/types';

/**
 * Unified "join / sign-in with a code" form.
 *
 * One entry point for BOTH code systems so a student never has to guess which
 * page to use:
 *  - **Org invite code** (e.g. SCHOOL2026): detected via validate-code.
 *      · student   → phone-based, passwordless (same as a class student)
 *      · admin/deputy/teacher → create an account (username + password)
 *  - **Class invite code** (teacher → student): phone + code passwordless login.
 *
 * Detection: we validate the code as an org code first. If no org code exists
 * with that value, we treat it as a class code and ask for the phone.
 */

type Step = 'code' | 'org-student' | 'org-account' | 'class' | 'redirecting';

const ROLE_INFO: Record<string, { label: string; icon: typeof ShieldCheck; color: string }> = {
  admin: { label: 'مدیر سازمان', icon: ShieldCheck, color: 'text-red-500' },
  deputy: { label: 'معاون', icon: UserCog, color: 'text-orange-500' },
  teacher: { label: 'معلم', icon: BookOpen, color: 'text-blue-500' },
  student: { label: 'دانش‌آموز', icon: GraduationCap, color: 'text-emerald-500' },
};

/** Mirror of the zod iranMobile transform so org + class phones normalize alike. */
function normalizeIranPhone(raw: string): string {
  const digits = String(raw ?? '').replace(/\D/g, '');
  if (digits.startsWith('98') && digits.length === 12) return `0${digits.slice(2)}`;
  if (digits.length === 10 && digits.startsWith('9')) return `0${digits}`;
  return digits;
}

function isValidIranPhone(normalized: string): boolean {
  return normalized.startsWith('09') && normalized.length === 11;
}

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

  // Account (manager / teacher)
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  // ── Routing after a successful org redeem ──
  const routeAfterOrg = (orgRole: string, slug: string) => {
    setStep('redirecting');
    if (orgRole === 'admin' || orgRole === 'deputy') {
      // A manager is NOT a platform admin — pre-select their org workspace so
      // /teacher opens in org (management) mode. (Do NOT send them to
      // /admin/organizations/... — the admin route group bounces non-admins.)
      try { localStorage.setItem(WORKSPACE_STORAGE_KEY, slug); } catch { /* ignore */ }
      router.push('/teacher');
    } else if (orgRole === 'teacher') {
      router.push('/teacher');
    } else {
      router.push('/home');
    }
  };

  // Persist tokens returned by an org redeem, then hydrate the user profile.
  const persistOrgSession = async (access?: string, refresh?: string) => {
    if (access) {
      persistTokens({ access, refresh: refresh ?? '' });
      try {
        const me = await fetchMe();
        persistUser(me);
      } catch {
        // Non-fatal: the access token is stored; the dashboard will hydrate.
      }
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
        // Already authenticated → redeem straight away (any role).
        if (result.needsRegistration === false) {
          await redeemOrgAuthenticated(trimmed);
          return;
        }
        setStep(result.targetRole === 'student' ? 'org-student' : 'org-account');
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

  // ── Org redeem (already-authenticated user) ──
  const redeemOrgAuthenticated = async (codeValue: string) => {
    setBusy(true);
    try {
      const res = await OrganizationService.redeemCode({ code: codeValue });
      toast.success(`به ${res.organization.name} خوش آمدید!`);
      routeAfterOrg(res.membership.orgRole, res.organization.slug);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در عضویت');
    } finally {
      setBusy(false);
    }
  };

  // ── Org student: phone-based, passwordless ──
  const handleOrgStudent = async () => {
    const normalized = normalizeIranPhone(phone);
    if (!isValidIranPhone(normalized)) {
      toast.error('شماره تماس معتبر نیست.');
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
      await persistOrgSession(res.access, res.refresh);
      toast.success(`به ${res.organization.name} خوش آمدید!`);
      routeAfterOrg(res.membership.orgRole, res.organization.slug);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در ورود');
    } finally {
      setBusy(false);
    }
  };

  // ── Org manager / teacher: account creation ──
  const handleOrgAccount = async () => {
    if (!firstName.trim() || !lastName.trim()) {
      toast.error('نام و نام خانوادگی الزامی است.');
      return;
    }
    if (username.trim().length < 3) {
      toast.error('نام کاربری باید حداقل ۳ کاراکتر باشد.');
      return;
    }
    if (password.length < 8) {
      toast.error('رمز عبور باید حداقل ۸ کاراکتر باشد.');
      return;
    }
    if (password !== confirmPassword) {
      toast.error('رمز عبور و تکرار آن یکسان نیست.');
      return;
    }
    setBusy(true);
    try {
      const res = await OrganizationService.redeemCode({
        code: code.trim(),
        username: username.trim(),
        password,
        first_name: firstName.trim(),
        last_name: lastName.trim(),
      });
      await persistOrgSession(res.access, res.refresh);
      toast.success(`حساب شما ساخته شد و به ${res.organization.name} پیوستید!`);
      routeAfterOrg(res.membership.orgRole, res.organization.slug);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در ثبت‌نام');
    } finally {
      setBusy(false);
    }
  };

  // ── Class invite: phone + code, passwordless ──
  const handleClass = async () => {
    const normalized = normalizeIranPhone(phone);
    if (!isValidIranPhone(normalized)) {
      toast.error('شماره تماس معتبر نیست.');
      return;
    }
    setBusy(true);
    try {
      const resp = await inviteLogin({ code: code.trim(), phone: normalized });
      persistTokens(resp.tokens);
      persistUser(resp.user);
      toast.success('ورود انجام شد');
      setStep('redirecting');
      router.push('/home');
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
    setUsername('');
    setPassword('');
    setConfirmPassword('');
  };

  const roleInfo = codeInfo?.targetRole ? ROLE_INFO[codeInfo.targetRole] : null;

  // ── Organization banner (shown on org steps) ──
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
          {step === 'code' && 'کد سازمان یا کد کلاسِ معلم خود را وارد کنید'}
          {step === 'org-student' && 'برای ورود، شماره موبایل خود را وارد کنید'}
          {step === 'org-account' && 'اطلاعات حساب خود را تکمیل کنید'}
          {step === 'class' && 'برای ورود به کلاس، شماره موبایل خود را وارد کنید'}
          {step === 'redirecting' && 'در حال انتقال به داشبورد...'}
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
                onChange={(e) => setCode(e.target.value.toUpperCase())}
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
              کد سازمان را مدیر مدرسه/مؤسسه به شما می‌دهد و کد کلاس را معلم. هر دو را در همین‌جا وارد کنید — خودش تشخیص می‌دهد.
            </p>
          </div>
        </div>
      )}

      {/* ── Step 2a: org student (phone, passwordless) ── */}
      {step === 'org-student' && (
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
              onChange={(e) => setPhone(e.target.value)}
              placeholder="09123456789"
              dir="ltr"
              className="rounded-xl text-center text-lg tracking-widest"
              disabled={busy}
              onKeyDown={(e) => e.key === 'Enter' && handleOrgStudent()}
            />
          </div>
          <Button className="w-full h-12 rounded-xl text-base" onClick={handleOrgStudent} disabled={busy || !phone.trim()}>
            {busy ? <><Loader2 className="ms-2 h-4 w-4 animate-spin" />در حال ورود...</> : 'ورود به سازمان'}
          </Button>
        </div>
      )}

      {/* ── Step 2b: org manager/teacher (account) ── */}
      {step === 'org-account' && (
        <div className="space-y-4">
          {orgBanner}
          <button type="button" onClick={resetToCode} className="flex items-center gap-1 text-sm text-muted-foreground hover:text-primary transition-colors">
            <ArrowRight className="w-4 h-4" /> تغییر کد
          </button>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-xs">نام *</Label>
              <Input value={firstName} onChange={(e) => setFirstName(e.target.value)} className="rounded-xl" disabled={busy} />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">نام خانوادگی *</Label>
              <Input value={lastName} onChange={(e) => setLastName(e.target.value)} className="rounded-xl" disabled={busy} />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">نام کاربری *</Label>
            <Input value={username} onChange={(e) => setUsername(e.target.value)} dir="ltr" className="rounded-xl text-left" disabled={busy} />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">رمز عبور *</Label>
            <div className="relative">
              <Lock className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                dir="ltr"
                className="pr-10 pl-10 rounded-xl text-left"
                disabled={busy}
              />
              <button type="button" onClick={() => setShowPassword((s) => !s)} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">تکرار رمز عبور *</Label>
            <Input
              type={showPassword ? 'text' : 'password'}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              dir="ltr"
              className="rounded-xl text-left"
              disabled={busy}
              onKeyDown={(e) => e.key === 'Enter' && handleOrgAccount()}
            />
          </div>
          <Button className="w-full h-12 rounded-xl text-base" onClick={handleOrgAccount} disabled={busy}>
            {busy ? <><Loader2 className="ms-2 h-4 w-4 animate-spin" />در حال ثبت‌نام...</> : 'ثبت‌نام و ورود'}
          </Button>
        </div>
      )}

      {/* ── Step 2c: class invite (phone, passwordless) ── */}
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
              onChange={(e) => setPhone(e.target.value)}
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
