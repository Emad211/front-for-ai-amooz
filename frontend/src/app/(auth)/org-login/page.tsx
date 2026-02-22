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
  User,
  Lock,
  Eye,
  EyeOff,
  ShieldCheck,
  GraduationCap,
  BookOpen,
  UserCog,
  CheckCircle2,
} from 'lucide-react';
import { OrganizationService } from '@/services/organization-service';
import { persistTokens, persistUser, fetchMe } from '@/services/auth-service';
import type { ValidateCodeResult } from '@/types';

const ROLE_INFO: Record<string, { label: string; icon: typeof ShieldCheck; color: string }> = {
  admin: { label: 'مدیر', icon: ShieldCheck, color: 'text-red-500' },
  deputy: { label: 'معاون', icon: UserCog, color: 'text-orange-500' },
  teacher: { label: 'معلم', icon: BookOpen, color: 'text-blue-500' },
  student: { label: 'دانش‌آموز', icon: GraduationCap, color: 'text-emerald-500' },
};

type Step = 'code' | 'register';

export default function OrgLoginPage() {
  const router = useRouter();

  // ── Step state ──
  const [step, setStep] = useState<Step>('code');

  // ── Code step ──
  const [code, setCode] = useState('');
  const [validating, setValidating] = useState(false);
  const [codeInfo, setCodeInfo] = useState<ValidateCodeResult | null>(null);

  // ── Register step ──
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // ── Validate code ──
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
        // Anonymous user → show registration form
        setStep('register');
      } else {
        // Authenticated user → directly redeem
        await handleRedeemAuthenticated(trimmed);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در بررسی کد');
    } finally {
      setValidating(false);
    }
  };

  // ── Redeem for authenticated user (already logged in) ──
  const handleRedeemAuthenticated = async (codeValue: string) => {
    setSubmitting(true);
    try {
      const result = await OrganizationService.redeemCode({ code: codeValue });
      toast.success(`به ${result.organization.name} خوش آمدید!`);
      redirectAfterJoin(result.membership.orgRole, result.organization.id);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در عضویت');
    } finally {
      setSubmitting(false);
    }
  };

  // ── Register + redeem for anonymous user ──
  const handleRegisterAndRedeem = async () => {
    // Validation
    if (!firstName.trim() || !lastName.trim()) {
      toast.error('نام و نام خانوادگی الزامی است.');
      return;
    }
    if (!username.trim() || username.trim().length < 3) {
      toast.error('نام کاربری باید حداقل ۳ کاراکتر باشد.');
      return;
    }
    if (!password || password.length < 6) {
      toast.error('رمز عبور باید حداقل ۶ کاراکتر باشد.');
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
        username: username.trim(),
        password,
        first_name: firstName.trim(),
        last_name: lastName.trim(),
      });

      // Persist JWT tokens from the redeem response
      if (result.access && result.refresh) {
        persistTokens({ access: result.access, refresh: result.refresh });

        // Fetch full user profile and persist
        const me = await fetchMe(result.access);
        persistUser(me);
      }

      toast.success(`حساب شما ساخته شد و به ${result.organization.name} پیوستید!`);
      redirectAfterJoin(result.membership.orgRole, result.organization.id);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در ثبت‌نام');
    } finally {
      setSubmitting(false);
    }
  };

  // ── Redirect based on org role ──
  const redirectAfterJoin = (orgRole: string, orgId: number) => {
    if (orgRole === 'admin' || orgRole === 'deputy') {
      // Org admin/deputy → org management dashboard
      router.push(`/admin/organizations/${orgId}`);
    } else if (orgRole === 'teacher') {
      router.push('/teacher');
    } else {
      router.push('/home');
    }
  };

  const roleInfo = codeInfo?.targetRole ? ROLE_INFO[codeInfo.targetRole] : null;
  const RoleIcon = roleInfo?.icon ?? Building2;

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
                {step === 'code'
                  ? 'کد فعالسازی یا دعوت سازمان را وارد کنید'
                  : 'اطلاعات خود را تکمیل کنید'}
              </p>
            </div>
          </CardHeader>

          <CardContent className="space-y-6 pb-8">
            {/* ── Step 1: Code Entry ── */}
            {step === 'code' && (
              <>
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

                <Separator />

                <div className="text-center space-y-2">
                  <p className="text-xs text-muted-foreground">
                    این کد توسط مدیر مدرسه یا مؤسسه آموزشی به شما ارسال شده است.
                  </p>
                  <p className="text-xs text-muted-foreground">
                    اگر کد ندارید، از{' '}
                    <Link href="/login" className="text-primary hover:underline font-medium">
                      ورود عادی
                    </Link>{' '}
                    استفاده کنید.
                  </p>
                </div>
              </>
            )}

            {/* ── Step 2: Registration Form ── */}
            {step === 'register' && codeInfo && (
              <>
                {/* Organization Info Banner */}
                <div className="rounded-xl bg-primary/5 border border-primary/10 p-4 space-y-3">
                  <div className="flex items-center gap-3">
                    {codeInfo.organization?.logo ? (
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
                        <Badge
                          variant="outline"
                          className="text-xs gap-1"
                        >
                          <RoleIcon className={`w-3 h-3 ${roleInfo?.color ?? ''}`} />
                          {codeInfo.targetRoleDisplay ?? roleInfo?.label}
                        </Badge>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Back button */}
                <button
                  type="button"
                  onClick={() => { setStep('code'); setCodeInfo(null); }}
                  className="flex items-center gap-1 text-sm text-muted-foreground hover:text-primary transition-colors"
                >
                  <ArrowRight className="w-4 h-4" />
                  تغییر کد
                </button>

                {/* Registration Form */}
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
                    <Label htmlFor="username">نام کاربری *</Label>
                    <div className="relative">
                      <User className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                      <Input
                        id="username"
                        value={username}
                        onChange={(e) => setUsername(e.target.value)}
                        placeholder="ali_ahmadi"
                        className="pr-10 h-11 bg-background/50 border-border/50"
                        dir="ltr"
                        disabled={submitting}
                      />
                    </div>
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
          حساب کاربری دارید؟{' '}
          <Link href="/login" className="text-primary hover:underline font-medium">
            ورود
          </Link>
        </p>
      </div>
    </div>
  );
}
