"use client";

import { useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2, KeyRound } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PasswordInput } from "@/components/auth/password-input";

import {
  passwordResetRequestSchema,
  passwordResetConfirmSchema,
  type PasswordResetRequestFormValues,
  type PasswordResetConfirmFormValues,
} from "@/lib/validations/auth";
import {
  ApiRequestError,
  normalizeApiError,
  persistTokens,
  persistUser,
  fetchMe,
  requestPasswordReset,
  confirmPasswordReset,
} from "@/services/auth-service";

function inputErrorClass(hasError: boolean) {
  return hasError ? "border-destructive focus-visible:ring-destructive" : "";
}

export default function ForgotPasswordPage() {
  const router = useRouter();
  const [step, setStep] = useState<"request" | "confirm">("request");
  const [identifier, setIdentifier] = useState("");

  const requestForm = useForm<PasswordResetRequestFormValues>({
    resolver: zodResolver(passwordResetRequestSchema),
    defaultValues: { identifier: "" },
  });

  const confirmForm = useForm<PasswordResetConfirmFormValues>({
    resolver: zodResolver(passwordResetConfirmSchema),
    defaultValues: { code: "", password: "", confirmPassword: "" },
  });

  async function onRequest(data: PasswordResetRequestFormValues) {
    try {
      await requestPasswordReset(data.identifier);
      setIdentifier(data.identifier);
      setStep("confirm");
      // Generic by design (no account enumeration).
      toast.success("اگر حسابی با این مشخصات باشد، کد بازیابی پیامک شد.");
    } catch (err) {
      const msg = err instanceof ApiRequestError ? normalizeApiError(err).message : "خطا در ارسال درخواست";
      toast.error(msg);
    }
  }

  async function onConfirm(data: PasswordResetConfirmFormValues) {
    try {
      const resp = await confirmPasswordReset({
        identifier,
        code: data.code,
        new_password: data.password,
      });
      if (resp.access && resp.refresh) {
        persistTokens({ access: resp.access, refresh: resp.refresh });
        try {
          const me = await fetchMe();
          persistUser(me);
          const role = (me.role || "").toLowerCase();
          const dest = role === "admin" ? "/admin" : role === "teacher" || role === "manager" ? "/teacher" : "/home";
          toast.success("رمز عبور تغییر کرد. وارد شدید.");
          router.push(dest);
          return;
        } catch {
          // fall through to login
        }
      }
      toast.success("رمز عبور با موفقیت تغییر کرد. وارد شوید.");
      router.push("/login");
    } catch (err) {
      if (err instanceof ApiRequestError) {
        const normalized = normalizeApiError(err);
        if (normalized.fieldErrors.new_password?.[0]) {
          confirmForm.setError("password", { type: "server", message: normalized.fieldErrors.new_password[0] });
        }
        toast.error(normalized.message);
        return;
      }
      toast.error(err instanceof Error ? err.message : "تغییر رمز با خطا مواجه شد");
    }
  }

  return (
    <div dir="rtl" className="flex min-h-screen flex-col items-center bg-background p-4 overflow-y-auto">
      <div className="w-full flex justify-start mb-8 sm:absolute sm:top-8 sm:start-8 sm:mb-0 sm:w-auto">
        <Link href="/" className="flex items-center gap-2 group relative">
          <div className="relative h-12 w-16">
            <Image src="/logo.png" alt="AI-Amooz logo" fill sizes="128px" className="object-contain transition-all duration-300 scale-[2.2] origin-center" priority />
          </div>
          <span className="text-xl font-bold text-text-light ml-2">AI-Amooz</span>
        </Link>
      </div>

      <div className="w-full max-w-md flex-1 flex flex-col justify-center">
        <div className="mb-6 text-center space-y-2">
          <div className="flex justify-center mb-2">
            <div className="p-3 rounded-2xl bg-primary/10">
              <KeyRound className="h-7 w-7 text-primary" />
            </div>
          </div>
          <h1 className="text-3xl font-black text-foreground">بازیابی رمز عبور</h1>
          <p className="text-sm text-muted-foreground leading-7">
            {step === "request"
              ? "نام کاربری یا ایمیل خود را وارد کنید تا کد بازیابی به شماره موبایل ثبت‌شده پیامک شود."
              : "کد پیامک‌شده و رمز عبور جدید خود را وارد کنید."}
          </p>
        </div>

        {step === "request" ? (
          <form onSubmit={requestForm.handleSubmit(onRequest)} className="space-y-4 bg-card/60 border border-border/80 rounded-2xl p-6 shadow-sm">
            <div className="space-y-2">
              <Label htmlFor="identifier">نام کاربری یا ایمیل</Label>
              <Input
                id="identifier"
                dir="ltr"
                autoComplete="username"
                disabled={requestForm.formState.isSubmitting}
                className={inputErrorClass(!!requestForm.formState.errors.identifier)}
                {...requestForm.register("identifier")}
              />
              {requestForm.formState.errors.identifier && (
                <p className="text-xs text-destructive">{requestForm.formState.errors.identifier.message}</p>
              )}
            </div>
            <Button type="submit" className="w-full h-12 text-base" disabled={requestForm.formState.isSubmitting}>
              {requestForm.formState.isSubmitting ? (
                <><Loader2 className="ms-2 h-4 w-4 animate-spin" /> در حال ارسال…</>
              ) : (
                "ارسال کد بازیابی"
              )}
            </Button>
          </form>
        ) : (
          <form onSubmit={confirmForm.handleSubmit(onConfirm)} className="space-y-4 bg-card/60 border border-border/80 rounded-2xl p-6 shadow-sm">
            <div className="space-y-2">
              <Label htmlFor="code">کد تأیید پیامک‌شده</Label>
              <Input
                id="code"
                dir="ltr"
                inputMode="numeric"
                autoComplete="one-time-code"
                placeholder="۶ رقم"
                disabled={confirmForm.formState.isSubmitting}
                className={inputErrorClass(!!confirmForm.formState.errors.code)}
                {...confirmForm.register("code")}
              />
              {confirmForm.formState.errors.code && (
                <p className="text-xs text-destructive">{confirmForm.formState.errors.code.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">رمز عبور جدید</Label>
              <PasswordInput
                id="password"
                autoComplete="new-password"
                disabled={confirmForm.formState.isSubmitting}
                className={inputErrorClass(!!confirmForm.formState.errors.password)}
                {...confirmForm.register("password")}
              />
              {confirmForm.formState.errors.password && (
                <p className="text-xs text-destructive">{confirmForm.formState.errors.password.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirmPassword">تکرار رمز عبور جدید</Label>
              <PasswordInput
                id="confirmPassword"
                autoComplete="new-password"
                disabled={confirmForm.formState.isSubmitting}
                className={inputErrorClass(!!confirmForm.formState.errors.confirmPassword)}
                {...confirmForm.register("confirmPassword")}
              />
              {confirmForm.formState.errors.confirmPassword && (
                <p className="text-xs text-destructive">{confirmForm.formState.errors.confirmPassword.message}</p>
              )}
            </div>
            <Button type="submit" className="w-full h-12 text-base" disabled={confirmForm.formState.isSubmitting}>
              {confirmForm.formState.isSubmitting ? (
                <><Loader2 className="ms-2 h-4 w-4 animate-spin" /> در حال تغییر رمز…</>
              ) : (
                "تغییر رمز و ورود"
              )}
            </Button>
            <button
              type="button"
              onClick={() => setStep("request")}
              className="w-full text-xs text-muted-foreground hover:text-foreground"
            >
              کد را دریافت نکردید؟ تلاش دوباره
            </button>
          </form>
        )}

        <p className="mt-6 text-sm text-center text-muted-foreground">
          <Link href="/login" className="font-semibold text-primary hover:underline">بازگشت به ورود</Link>
        </p>
      </div>
    </div>
  );
}
