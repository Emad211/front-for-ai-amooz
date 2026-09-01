'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import Image from 'next/image';
import { ShieldCheck, Smartphone } from 'lucide-react';

import { requestLoginOtp, verifyLoginOtp } from '@/services/parent-service';
import { toEnglishDigits, toPersianDigits } from '@/lib/persian-digits';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

/** Resend window in seconds — mirrors the backend's OTP validity window. */
const RESEND_COOLDOWN_SECONDS = 90;

/**
 * ورود والدین — the PUBLIC phone+OTP entry for the parent digest panel.
 *
 * Deliberately top-level (no route-group layout): a parent has no dashboard
 * shell, only this screen and /parent. Both steps live on ONE screen because
 * a low-tech-literacy user must never lose context to a navigation — the
 * second step simply replaces the first inside the same card.
 *
 * Everything is oversized on purpose: h-14 inputs, h-12 buttons, text-base+
 * copy, and digits typed with a Persian keyboard (۰-۹) are normalized.
 */
export default function ParentLoginPage() {
  const router = useRouter();
  const otpInputRef = useRef<HTMLInputElement>(null);

  const [step, setStep] = useState<'phone' | 'otp'>('phone');
  const [phone, setPhone] = useState('');
  const [otp, setOtp] = useState('');
  const [error, setError] = useState('');
  const [sending, setSending] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [cooldown, setCooldown] = useState(0);

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = window.setInterval(() => {
      setCooldown((remaining) => (remaining > 0 ? remaining - 1 : 0));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [cooldown]);

  useEffect(() => {
    if (step === 'otp') otpInputRef.current?.focus();
  }, [step]);

  // Persian-tolerant digit hygiene: ۰-۹/٠-٩ → 0-9, non-digits stripped.
  const englishPhone = toEnglishDigits(phone).replace(/\D/g, '');
  const englishOtp = toEnglishDigits(otp).replace(/\D/g, '');

  const handlePhoneChange = (value: string) => {
    setPhone(toEnglishDigits(value).replace(/\D/g, '').slice(0, 11));
    setError('');
  };

  const handleOtpChange = (value: string) => {
    setOtp(toEnglishDigits(value).replace(/\D/g, '').slice(0, 6));
    setError('');
  };

  const requestCode = async (nextPhone: string): Promise<boolean> => {
    setSending(true);
    setError('');
    try {
      await requestLoginOtp(nextPhone);
      return true;
    } catch (err: unknown) {
      // Persian `detail` from the server — verbatim, no re-wrapping.
      setError(err instanceof Error ? err.message : 'ارسال کد ناموفق بود.');
      return false;
    } finally {
      setSending(false);
    }
  };

  const handleSendCode = async () => {
    if (!/^09\d{9}$/.test(englishPhone)) {
      setError('شماره موبایل را به شکل ۰۹۱۲۳۴۵۶۷۸۹ وارد کنید.');
      return;
    }
    const ok = await requestCode(englishPhone);
    if (ok) {
      setOtp('');
      setStep('otp');
      setCooldown(RESEND_COOLDOWN_SECONDS);
    }
  };

  const handleResend = async () => {
    const ok = await requestCode(englishPhone);
    if (ok) {
      setOtp('');
      setCooldown(RESEND_COOLDOWN_SECONDS);
    }
  };

  const handleVerify = async () => {
    if (englishOtp.length !== 6) {
      setError('کد ۶ رقمی پیامک‌شده را کامل وارد کنید.');
      return;
    }
    setVerifying(true);
    setError('');
    try {
      await verifyLoginOtp(englishPhone, englishOtp);
      router.replace('/parent');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'ورود ناموفق بود.');
    } finally {
      setVerifying(false);
    }
  };

  return (
    <div
      dir="rtl"
      className="flex min-h-screen flex-col items-center bg-background p-4"
    >
      <div className="mb-8 flex w-full justify-start sm:absolute sm:top-8 sm:start-8 sm:w-auto">
        <Link href="/" className="relative flex items-center gap-2">
          <div className="relative h-12 w-16">
            <Image
              src="/logo.png"
              alt="آی‌اموز"
              fill
              sizes="128px"
              className="scale-[2.2] origin-center object-contain transition-all duration-300"
              priority
            />
          </div>
          <span className="text-xl font-bold text-foreground">AI-Amooz</span>
        </Link>
      </div>

      <div className="flex w-full max-w-md flex-1 flex-col justify-center">
        <div className="rounded-2xl border border-border/50 bg-card p-6 sm:p-8">
          <h1 className="text-center text-2xl font-bold text-foreground">
            ورود والدین
          </h1>
          <p className="mt-2 text-center text-base leading-relaxed text-muted-foreground">
            گزارش هفتگی مطالعهٔ فرزندتان را ببینید.
          </p>

          {step === 'phone' ? (
            <form
              className="mt-8 space-y-4"
              onSubmit={(e) => {
                e.preventDefault();
                if (!sending) void handleSendCode();
              }}
            >
              <div className="space-y-2">
                <label
                  htmlFor="parent-phone"
                  className="block text-base font-medium text-foreground"
                >
                  شماره موبایل
                </label>
                <div className="relative">
                  <Smartphone className="absolute right-3 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    id="parent-phone"
                    type="tel"
                    inputMode="tel"
                    autoComplete="tel"
                    dir="ltr"
                    placeholder="۰۹۱۲۳۴۵۶۷۸۹"
                    value={phone}
                    onChange={(e) => handlePhoneChange(e.target.value)}
                    disabled={sending}
                    className="h-14 rounded-xl bg-background px-4 pr-11 text-left text-lg tabular-nums"
                  />
                </div>
              </div>

              <Button
                type="submit"
                disabled={sending || phone.length === 0}
                className="h-12 w-full rounded-xl text-base font-bold"
              >
                {sending ? 'در حال ارسال کد…' : 'ارسال کد'}
              </Button>
            </form>
          ) : (
            <form
              className="mt-8 space-y-4"
              onSubmit={(e) => {
                e.preventDefault();
                if (!verifying) void handleVerify();
              }}
            >
              <div className="space-y-2">
                <label
                  htmlFor="parent-otp"
                  className="block text-base font-medium text-foreground"
                >
                  کد ۶ رقمی پیامک‌شده
                </label>
                <div className="relative">
                  <ShieldCheck className="absolute right-3 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    id="parent-otp"
                    ref={otpInputRef}
                    type="text"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    dir="ltr"
                    placeholder="------"
                    value={otp}
                    onChange={(e) => handleOtpChange(e.target.value)}
                    disabled={verifying}
                    className="h-14 rounded-xl bg-background px-4 pr-11 text-center text-2xl font-bold tracking-widest tabular-nums"
                  />
                </div>
                <p className="text-sm text-muted-foreground">
                  کد به شماره {toPersianDigits(englishPhone)} پیامک شد.
                </p>
              </div>

              <Button
                type="submit"
                disabled={verifying || englishOtp.length !== 6}
                className="h-12 w-full rounded-xl text-base font-bold"
              >
                {verifying ? 'در حال بررسی…' : 'ورود'}
              </Button>

              <div className="flex flex-col items-center gap-2 pt-1">
                {cooldown > 0 ? (
                  <p className="text-sm text-muted-foreground">
                    درخواست کد جدید تا {toPersianDigits(cooldown)} ثانیه دیگر
                    ممکن است.
                  </p>
                ) : (
                  <Button
                    type="button"
                    variant="ghost"
                    disabled={sending}
                    onClick={() => void handleResend()}
                    className="h-11 rounded-xl px-4 text-base font-medium text-primary"
                  >
                    {sending ? 'در حال ارسال…' : 'ارسال مجدد کد'}
                  </Button>
                )}
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => {
                    setStep('phone');
                    setOtp('');
                    setCooldown(0);
                    setError('');
                  }}
                  className="h-11 rounded-xl px-4 text-base text-muted-foreground"
                >
                  ویرایش شماره موبایل
                </Button>
              </div>
            </form>
          )}

          {error && (
            <p
              role="alert"
              aria-live="polite"
              className="mt-4 rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-3 text-base leading-relaxed text-destructive"
            >
              {error}
            </p>
          )}
        </div>

        <p className="mt-6 text-center text-sm leading-relaxed text-muted-foreground">
          حساب کاربری ندارید؟ مشاور فرزند شما شماره‌تان را ثبت می‌کند و کد
          ورود برایتان پیامک می‌شود.
        </p>
      </div>
    </div>
  );
}
