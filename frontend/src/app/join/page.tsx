'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { OrganizationService } from '@/services/organization-service';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { Building2, KeyRound, ArrowLeft, CheckCircle } from 'lucide-react';
import { PageTransition } from '@/components/ui/page-transition';
import type { ValidateCodeResult } from '@/types';

type Step = 'enter-code' | 'confirm' | 'register' | 'success';

export default function JoinOrgPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>('enter-code');
  const [code, setCode] = useState('');
  const [validationResult, setValidationResult] = useState<ValidateCodeResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // Registration fields (for unauthenticated users)
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');

  // Success data
  const [successOrg, setSuccessOrg] = useState<{ name: string; slug: string } | null>(null);

  const handleValidate = async () => {
    if (!code.trim()) {
      toast.error('لطفاً کد دعوت را وارد کنید.');
      return;
    }
    try {
      setIsLoading(true);
      const result = await OrganizationService.validateCode(code.trim());
      setValidationResult(result);
      if (result.valid) {
        setStep(result.needsRegistration ? 'register' : 'confirm');
      } else {
        toast.error(result.detail || 'کد نامعتبر است.');
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا');
    } finally {
      setIsLoading(false);
    }
  };

  const handleRedeem = async () => {
    try {
      setIsLoading(true);
      const payload: Parameters<typeof OrganizationService.redeemCode>[0] = {
        code: code.trim(),
      };
      if (validationResult?.needsRegistration) {
        payload.username = username;
        payload.password = password;
        payload.first_name = firstName;
        payload.last_name = lastName;
      }
      const result = await OrganizationService.redeemCode(payload);

      // If new account was created, store tokens
      if (result.access && result.refresh) {
        localStorage.setItem('ai_amooz_access', result.access);
        localStorage.setItem('ai_amooz_refresh', result.refresh);
      }

      setSuccessOrg(result.organization);
      setStep('success');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <PageTransition>
      <div className="min-h-screen flex items-center justify-center bg-background p-4" dir="rtl">
        <Card className="w-full max-w-md rounded-2xl shadow-xl">
          {/* ── Step 1: Enter Code ── */}
          {step === 'enter-code' && (
            <>
              <CardHeader className="text-center pb-4">
                <div className="w-14 h-14 rounded-2xl bg-primary/10 flex items-center justify-center mx-auto mb-4">
                  <KeyRound className="w-7 h-7 text-primary" />
                </div>
                <CardTitle className="text-xl font-black">عضویت در سازمان</CardTitle>
                <p className="text-sm text-muted-foreground mt-1">
                  کد دعوتی که از سازمان دریافت کرده‌اید را وارد کنید
                </p>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label>کد دعوت</Label>
                  <Input
                    value={code}
                    onChange={(e) => setCode(e.target.value.toUpperCase())}
                    placeholder="مثلاً: SCHOOL2026"
                    dir="ltr"
                    className="text-center text-lg font-mono tracking-widest rounded-xl"
                    onKeyDown={(e) => e.key === 'Enter' && handleValidate()}
                  />
                </div>
                <Button
                  className="w-full rounded-xl"
                  onClick={handleValidate}
                  disabled={isLoading}
                >
                  {isLoading ? 'در حال بررسی...' : 'بررسی کد'}
                </Button>
                <div className="text-center">
                  <a href="/login" className="text-sm text-primary hover:underline">
                    بازگشت به ورود
                  </a>
                </div>
              </CardContent>
            </>
          )}

          {/* ── Step 2: Confirm (authenticated user) ── */}
          {step === 'confirm' && validationResult?.organization && (
            <>
              <CardHeader className="text-center pb-4">
                <div className="w-14 h-14 rounded-2xl bg-primary/10 flex items-center justify-center mx-auto mb-4">
                  <Building2 className="w-7 h-7 text-primary" />
                </div>
                <CardTitle className="text-xl font-black">تأیید عضویت</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="bg-muted/50 rounded-xl p-4 text-center space-y-2">
                  {validationResult.organization.logo && (
                    <img
                      src={validationResult.organization.logo}
                      alt=""
                      className="w-12 h-12 rounded-xl mx-auto object-cover"
                    />
                  )}
                  <p className="font-bold text-lg">{validationResult.organization.name}</p>
                  <Badge variant="secondary">{validationResult.targetRoleDisplay}</Badge>
                </div>
                <p className="text-sm text-center text-muted-foreground">
                  آیا می‌خواهید به این سازمان بپیوندید؟
                </p>
                <div className="flex gap-3">
                  <Button
                    variant="outline"
                    className="flex-1 rounded-xl"
                    onClick={() => { setStep('enter-code'); setValidationResult(null); }}
                  >
                    انصراف
                  </Button>
                  <Button
                    className="flex-1 rounded-xl"
                    onClick={handleRedeem}
                    disabled={isLoading}
                  >
                    {isLoading ? 'در حال عضویت...' : 'عضویت'}
                  </Button>
                </div>
              </CardContent>
            </>
          )}

          {/* ── Step 3: Register (unauthenticated user) ── */}
          {step === 'register' && validationResult?.organization && (
            <>
              <CardHeader className="pb-4">
                <div className="flex items-center gap-3">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="rounded-xl"
                    onClick={() => { setStep('enter-code'); setValidationResult(null); }}
                  >
                    <ArrowLeft className="w-4 h-4" />
                  </Button>
                  <div>
                    <CardTitle className="text-lg font-black">ثبت‌نام و عضویت</CardTitle>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {validationResult.organization.name} · {validationResult.targetRoleDisplay}
                    </p>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <Label className="text-xs">نام</Label>
                    <Input
                      value={firstName}
                      onChange={(e) => setFirstName(e.target.value)}
                      className="rounded-xl"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-xs">نام خانوادگی</Label>
                    <Input
                      value={lastName}
                      onChange={(e) => setLastName(e.target.value)}
                      className="rounded-xl"
                    />
                  </div>
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs">نام کاربری *</Label>
                  <Input
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    dir="ltr"
                    className="rounded-xl text-left"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs">رمز عبور *</Label>
                  <Input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    dir="ltr"
                    className="rounded-xl text-left"
                  />
                </div>
                <Button
                  className="w-full rounded-xl"
                  onClick={handleRedeem}
                  disabled={isLoading || !username.trim() || !password.trim()}
                >
                  {isLoading ? 'در حال ثبت‌نام...' : 'ثبت‌نام و عضویت'}
                </Button>
              </CardContent>
            </>
          )}

          {/* ── Step 4: Success ── */}
          {step === 'success' && successOrg && (
            <>
              <CardHeader className="text-center pb-4">
                <div className="w-14 h-14 rounded-2xl bg-emerald-500/10 flex items-center justify-center mx-auto mb-4">
                  <CheckCircle className="w-7 h-7 text-emerald-500" />
                </div>
                <CardTitle className="text-xl font-black">عضویت موفق!</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4 text-center">
                <p className="text-sm text-muted-foreground">
                  شما با موفقیت به <strong>{successOrg.name}</strong> پیوستید.
                </p>
                <Button
                  className="w-full rounded-xl"
                  onClick={() => router.push('/home')}
                >
                  ورود به داشبورد
                </Button>
              </CardContent>
            </>
          )}
        </Card>
      </div>
    </PageTransition>
  );
}
