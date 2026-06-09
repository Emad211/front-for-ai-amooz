'use client';

import { useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import {
  Building2,
  KeyRound,
  Loader2,
  ArrowRight,
  Lock,
  Eye,
  EyeOff,
  ShieldCheck,
  GraduationCap,
  BookOpen,
  UserCog,
  CheckCircle2,
  Smartphone,
  LogIn,
} from 'lucide-react';
import { OrganizationService } from '@/services/organization-service';
import {
  persistTokens,
  persistUser,
  fetchMe,
  login as loginRequest,
  getStoredUser,
  landingPathForRole,
} from '@/services/auth-service';
import type { ValidateCodeResult } from '@/types';

const ROLE_INFO: Record<string, { label: string; icon: typeof ShieldCheck; color: string }> = {
  admin: { label: 'مدیر', icon: ShieldCheck, color: 'text-red-500' },
  deputy: { label: 'معاون', icon: UserCog, color: 'text-orange-500' },
  teacher: { label: 'معلم', icon: BookOpen, color: 'text-blue-500' },
  student: { label: 'دانش‌آموز', icon: GraduationCap, color: 'text-emerald-500' },
};

// 'login'  → returning org member signs in with mobile/email + password
// 'join'   → first-time member redeems an invite code (validate → register)
type Mode = 'login' | 'join';
type JoinStep = 'code' | 'register';

export default function OrgLoginPage() {
  const router = useRouter();

  const [mode, setMode] = useState<Mode>('login');

  // ── Login mode ──
  const [loginId, setLoginId] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [loggingIn, setLoggingIn] = useState(false);

  // ── Join mode ──
  const [joinStep, setJoinStep] = useState<JoinStep>('code');
  const [code, setCode] = useState('');
  const [validating, setValidating] = useState(false);
  const [codeInfo, setCodeInfo] = useState<ValidateCodeResult | null>(null);

  // ── Register fields (join → register step) ──
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // ── Shared: persist a fresh profile (if we just got a token) and route by role ──
  const finishAndRoute = async (opts: { accessToken?: string; orgRole?: string; orgSlug?: string }) => {
    const { accessToken, orgRole, orgSlug } = opts;
    // Pre-select the org workspace so the dashboard opens in org mode.
    if (orgSlug && orgRole && orgRole !== 'student') {
      try {
        window.localStorage.setItem('ai_amooz_active_workspace', orgSlug);
      } catch {
        /* non-fatal */
      }
    }
    let role: string | undefined;
    if (accessToken) {
      const me = await fetchMe(accessToken);
      persistUser(me);
      role = me.role;
    } else {
      role = getStoredUser()?.role ?? undefined;
    }
    router.push(landingPathForRole(role));
  };

  // ── LOGIN ──
  const handleLogin = async () => {
    const identifier = loginId.trim();
    if (!identifier || !loginPassword) {
      toast.error('شماره موبایل/ایمیل و رمز عبور را وارد کنید.');
      return;
    }
    setLoggingIn(true);
    try {
      const tokens = await loginRequest({ username: identifier, password: loginPassword });
      persistTokens(tokens);
      toast.success('ورود با موفقیت انجام شد');
      await finishAndRoute({ accessToken: tokens.access });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'نام کاربری یا رمز عبور نادرست است.');
    } finally {
      setLoggingIn(false);
    }
  };

  // ── JOIN: validate code ──
  const handleValidateCode = async () => {
    const trimmed = code.trim();
    if (!trimmed) {
      toast.error('لطفاً کد را وارد کنید.');
      return;
    }
    setValidating(true);
    try {
      const result = await OrganizationService.validateCode(trimmed);
      if (!result.valid) {
        toast.error(result.detail ?? 'کد نامعتبر است.');
        return;
      }
      setCodeInfo(result);
      if (result.needsRegistration) {
        setJoinStep('register');
      } else {
        // Already authenticated → just join the org with the current account.
        await handleRedeemAuthenticated(trimmed, result.targetRole);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در بررسی کد');
    } finally {
      setValidating(false);
    }
  };

  // ── JOIN: redeem for an already-authenticated user ──
  const handleRedeemAuthenticated = async (codeValue: string, targetRole?: string) => {
    setSubmitting(true);
    try {
      const result = await OrganizationService.redeemCode({ code: codeValue });
      toast.success(`به ${result.organization.name} خوش آمدید!`);
      await finishAndRoute({
        orgRole: targetRole ?? result.membership.orgRole,
        orgSlug: result.organization.slug,
      });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در عضویت');
    } finally {
      setSubmitting(false);
    }
  };

  // ── JOIN: register + redeem for a new user ──
  const handleRegisterAndRedeem = async () => {
    if (!firstName.trim() || !lastName.trim()) {
      toast.error('نام و نام خانوادگی الزامی است.');
      return;
    }
    const normalizedPhone = phone.replace(/\D/g, '');
    if (!/^09\d{9}$/.test(normalizedPhone)) {
      toast.error('شماره موبایل معتبر نیست (مثال: ۰۹۱۲۳۴۵۶۷۸۹).');
      return;
    }
    if (!password || password.length < 8) {
      toast.error('رمز عبور باید حداقل ۸ کاراکتر باشد.');
      return;
    }
    if (password !== confirmPassword) {
      toast.error('رمز عبور و تکرار آن یکسان نیست.');
      return;
    }

    setSubmitting(true);
    try {
      const result = await OrganizationService.redeemCode({
        code: code.trim(),
        phone: normalizedPhone,
        password,
        first_name: firstName.trim(),
        last_name: lastName.trim(),
      });

      if (result.access && result.refresh) {
        persistTokens({ access: result.access, refresh: result.refresh });
        toast.success(`حساب شما ساخته شد و به ${result.organization.name} پیوستید!`);
        await finishAndRoute({
          accessToken: result.access,
          orgRole: result.membership.orgRole,
          orgSlug: result.organization.slug,
        });
      } else {
        // No token returned (shouldn't happen for a new account) — send to login.
        toast.success('حساب شما ساخته شد. اکنون وارد شوید.');
        setMode('login');
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'خطا در ثبت‌نام';
      // A pre-existing account can't "register" again — guide them to login.
      if (/قبل|already|ثبت\s*شده/i.test(message)) {
        toast.error('این حساب قبلاً ساخته شده است. لطفاً وارد شوید.');
        setMode('login');
        setLoginId(phone.replace(/\D/g, ''));
      } else {
        toast.error(message);
      }
    } finally {
      setSubmitting(false);
    }
  };

  const roleInfo = codeInfo?.targetRole ? ROLE_INFO[codeInfo.targetRole] : null;
  const RoleIcon = roleInfo?.icon ?? Building2;

  const resetJoin = () => {
    setJoinStep('code');
    setCodeInfo(null);
  };

  return (
    <div
      dir="rtl"
      className="min-h-screen bg-gradient-to-br from-primary/5 via-background to-primary/10 flex flex-col items-center p-4 overflow-y-auto"
    >
      {/* Background Effects */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 right-0 w-72 h-72 bg-primary/10 rounded-full blur-3xl" />
        <div className="absolute bottom-0 left-0 w-96 h-96 bg-primary/5 rounded-full blur-3xl" />
      </div>

      {/* Top Bar */}
      <div className="w-full flex justify-between items-center mb-8 z-10">
        <Link href="/" className="flex items-center gap-2 group">
          <div className="relative h-12 w-16">
            <Image
              src="/logo.png"
              alt="AI-Amooz logo"
              fill
              sizes="128px"
              className="object-contain transition-all duration-300 scale-[2.2] origin-center"
              priority
            />
          </div>
          <span className="text-xl font-bold text-foreground">AI-Amooz</span>
        </Link>
        <Link
          href="/login"
          className="text-sm text-muted-foreground hover:text-primary transition-colors"
        >
          ← ورود عادی
        </Link>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex items-center justify-center w-full z-10">
        <Card className="w-full max-w-md bg-card/80 backdrop-blur-xl border-border/50 shadow-2xl">
          <CardHeader className="space-y-4 text-center pb-6">
            <div className="flex justify-center">
              <div className="relative p-4 rounded-2xl bg-primary/10">
                <Building2 className="w-8 h-8 text-primary" />
              </div>
            </div>
            <div className="space-y-2">
              <h1 className="text-2xl font-bold text-foreground">ورود سازمانی</h1>
              <p className="text-muted-foreground text-sm">
                {mode === 'login'
                  ? 'با شماره موبایل و رمز عبور خود وارد شوید'
                  : joinStep === 'code'
                    ? 'کد فعالسازی یا دعوت سازمان را وارد کنید'
                    : 'اطلاعات خود را تکمیل کنید'}
              </p>
            </div>
          </CardHeader>

          <CardContent className="space-y-6 pb-8">
            {/* ════ LOGIN MODE ════ */}
            {mode === 'login' && (
              <>
                <div className="space-y-2">
                  <Label htmlFor="org-login-id" className="text-sm font-medium">
                    شماره موبایل یا ایمیل
                  </Label>
                  <div className="relative">
                    <Smartphone className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                    <Input
                      id="org-login-id"
                      type="text"
                      value={loginId}
                      onChange={(e) => setLoginId(e.target.value)}
                      placeholder="09123456789"
                      className="pr-10 h-12 bg-background/50 border-border/50"
                      dir="ltr"
                      inputMode="text"
                      autoComplete="username"
                      disabled={loggingIn}
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="org-login-pass" className="text-sm font-medium">
                    رمز عبور
                  </Label>
                  <div className="relative">
                    <Lock className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                    <Input
                      id="org-login-pass"
                      type={showPassword ? 'text' : 'password'}
                      value={loginPassword}
                      onChange={(e) => setLoginPassword(e.target.value)}
                      placeholder="••••••••"
                      className="pr-10 pl-10 h-12 bg-background/50 border-border/50"
                      dir="ltr"
                      autoComplete="current-password"
                      disabled={loggingIn}
                      onKeyDown={(e) => e.key === 'Enter' && handleLogin()}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    >
                      {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                <Button
                  onClick={handleLogin}
                  disabled={loggingIn || !loginId.trim() || !loginPassword}
                  className="w-full h-12 text-base"
                >
                  {loggingIn ? (
                    <>
                      <Loader2 className="ml-2 h-4 w-4 animate-spin" />
                      در حال ورود...
                    </>
                  ) : (
                    <>
                      <LogIn className="ml-2 h-4 w-4" />
                      ورود
                    </>
                  )}
                </Button>

                <Separator />

                <div className="text-center">
                  <p className="text-xs text-muted-foreground mb-2">
                    اولین بار است که به سازمان می‌پیوندید؟
                  </p>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => { setMode('join'); resetJoin(); }}
                    className="w-full h-11"
                  >
                    <KeyRound className="ml-2 h-4 w-4" />
                    ثبت‌نام با کد دعوت
                  </Button>
                </div>
              </>
            )}

            {/* ════ JOIN MODE — Step: code ════ */}
            {mode === 'join' && joinStep === 'code' && (
              <>
                <button
                  type="button"
                  onClick={() => setMode('login')}
                  className="flex items-center gap-1 text-sm text-muted-foreground hover:text-primary transition-colors"
                >
                  <ArrowRight className="w-4 h-4" />
                  بازگشت به ورود
                </button>

                <div className="space-y-2">
                  <Label htmlFor="org-code" className="text-sm font-medium">
                    کد فعالسازی / دعوت
                  </Label>
                  <div className="relative">
                    <KeyRound className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                    <Input
                      id="org-code"
                      type="text"
                      value={code}
                      onChange={(e) => setCode(e.target.value.toUpperCase())}
                      placeholder="ABCD12"
                      className="pr-10 h-12 bg-background/50 border-border/50 text-center text-lg tracking-widest font-mono"
                      dir="ltr"
                      disabled={validating}
                      onKeyDown={(e) => e.key === 'Enter' && handleValidateCode()}
                    />
                  </div>
                </div>

                <Button
                  onClick={handleValidateCode}
                  disabled={validating || !code.trim()}
                  className="w-full h-12 text-base"
                >
                  {validating ? (
                    <>
                      <Loader2 className="ml-2 h-4 w-4 animate-spin" />
                      در حال بررسی...
                    </>
                  ) : (
                    'ادامه'
                  )}
                </Button>

                <p className="text-xs text-muted-foreground text-center">
                  این کد توسط مدیر مدرسه یا مؤسسه آموزشی به شما ارسال شده است.
                </p>
              </>
            )}

            {/* ════ JOIN MODE — Step: register ════ */}
            {mode === 'join' && joinStep === 'register' && codeInfo && (
              <>
                <div className="rounded-xl bg-primary/5 border border-primary/10 p-4 space-y-3">
                  <div className="flex items-center gap-3">
                    {codeInfo.organization?.logo ? (
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
                      <p className="font-bold text-foreground">{codeInfo.organization?.name}</p>
                      <div className="flex items-center gap-2 mt-1">
                        <Badge variant="outline" className="text-xs gap-1">
                          <RoleIcon className={`w-3 h-3 ${roleInfo?.color ?? ''}`} />
                          {codeInfo.targetRoleDisplay ?? roleInfo?.label}
                        </Badge>
                      </div>
                    </div>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={resetJoin}
                  className="flex items-center gap-1 text-sm text-muted-foreground hover:text-primary transition-colors"
                >
                  <ArrowRight className="w-4 h-4" />
                  تغییر کد
                </button>

                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-2">
                      <Label htmlFor="first-name">نام *</Label>
                      <Input
                        id="first-name"
                        value={firstName}
                        onChange={(e) => setFirstName(e.target.value)}
                        placeholder="علی"
                        className="h-11 bg-background/50 border-border/50"
                        disabled={submitting}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="last-name">نام خانوادگی *</Label>
                      <Input
                        id="last-name"
                        value={lastName}
                        onChange={(e) => setLastName(e.target.value)}
                        placeholder="احمدی"
                        className="h-11 bg-background/50 border-border/50"
                        disabled={submitting}
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="phone">شماره موبایل *</Label>
                    <div className="relative">
                      <Smartphone className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                      <Input
                        id="phone"
                        value={phone}
                        onChange={(e) => setPhone(e.target.value)}
                        placeholder="09123456789"
                        className="pr-10 h-11 bg-background/50 border-border/50"
                        dir="ltr"
                        inputMode="numeric"
                        disabled={submitting}
                      />
                    </div>
                    <p className="text-[11px] text-muted-foreground">
                      شماره موبایل شما، نام کاربری ورود خواهد بود.
                    </p>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="password">رمز عبور *</Label>
                    <div className="relative">
                      <Lock className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                      <Input
                        id="password"
                        type={showPassword ? 'text' : 'password'}
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        placeholder="••••••••"
                        className="pr-10 pl-10 h-11 bg-background/50 border-border/50"
                        dir="ltr"
                        disabled={submitting}
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                      >
                        {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      </button>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="confirm-password">تکرار رمز عبور *</Label>
                    <div className="relative">
                      <Lock className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                      <Input
                        id="confirm-password"
                        type={showPassword ? 'text' : 'password'}
                        value={confirmPassword}
                        onChange={(e) => setConfirmPassword(e.target.value)}
                        placeholder="••••••••"
                        className="pr-10 h-11 bg-background/50 border-border/50"
                        dir="ltr"
                        disabled={submitting}
                      />
                    </div>
                  </div>
                </div>

                <Button
                  onClick={handleRegisterAndRedeem}
                  disabled={submitting}
                  className="w-full h-12 text-base"
                >
                  {submitting ? (
                    <>
                      <Loader2 className="ml-2 h-4 w-4 animate-spin" />
                      در حال ثبت‌نام...
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="ml-2 h-4 w-4" />
                      ثبت‌نام و ورود
                    </>
                  )}
                </Button>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Footer */}
      <div className="mt-8 text-center z-10">
        <p className="text-xs text-muted-foreground">
          حساب عادی دارید؟{' '}
          <Link href="/login" className="text-primary hover:underline font-medium">
            ورود عادی
          </Link>
        </p>
      </div>
    </div>
  );
}
