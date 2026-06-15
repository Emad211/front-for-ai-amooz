"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { AlertTriangle, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import {
  completeRegistrationSchema,
  type CompleteRegistrationFormValues,
} from "@/lib/validations/auth";
import { ApiRequestError, normalizeApiError, persistTokens, persistUser } from "@/services/auth-service";
import { completeTeacherRegistration } from "@/services/waitlist-service";

function inputErrorClass(hasError: boolean) {
  return hasError ? "border-destructive focus-visible:ring-destructive" : "";
}

function CompleteRegistrationInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";

  const {
    register,
    handleSubmit,
    setError,
    setFocus,
    formState: { errors, isSubmitting },
  } = useForm<CompleteRegistrationFormValues>({
    resolver: zodResolver(completeRegistrationSchema),
    mode: "onTouched",
    defaultValues: { username: "", password: "", confirmPassword: "" },
  });

  async function onSubmit(data: CompleteRegistrationFormValues) {
    try {
      const response = await completeTeacherRegistration({
        token,
        username: data.username,
        password: data.password,
      });
      persistTokens(response.tokens);
      persistUser(response.user);
      toast.success("حساب معلم شما ساخته شد. به پنل هدایت می‌شوید.");
      router.push("/teacher");
    } catch (err) {
      if (err instanceof ApiRequestError) {
        const normalized = normalizeApiError(err);
        const fieldMap: Record<string, keyof CompleteRegistrationFormValues | undefined> = {
          username: "username",
          password: "password",
        };
        let firstFocus: keyof CompleteRegistrationFormValues | null = null;
        let applied = false;
        for (const [backendField, messages] of Object.entries(normalized.fieldErrors)) {
          const formField = fieldMap[backendField];
          if (!formField) continue;
          applied = true;
          setError(formField, { type: "server", message: messages?.[0] ?? "مقدار نامعتبر است" });
          if (!firstFocus) firstFocus = formField;
        }
        if (firstFocus) setFocus(firstFocus);
        // Token errors arrive as a top-level `detail` (no field), so surface the message.
        toast.error(applied ? "لطفاً خطاهای فرم را بررسی کنید" : normalized.message);
        return;
      }
      toast.error(err instanceof Error ? err.message : "ثبت‌نام با خطا مواجه شد");
    }
  }

  if (!token) {
    return (
      <div className="bg-card/60 border border-border/80 rounded-2xl p-8 shadow-sm text-center space-y-4">
        <div className="flex justify-center">
          <div className="p-4 rounded-2xl bg-destructive/10">
            <AlertTriangle className="h-10 w-10 text-destructive" />
          </div>
        </div>
        <h1 className="text-2xl font-black text-foreground">لینک نامعتبر است</h1>
        <p className="text-sm text-muted-foreground leading-7">
          این صفحه فقط با لینک ثبت‌نامی که پس از تأیید برایتان ارسال شده باز می‌شود.
        </p>
        <Button asChild variant="outline" className="w-full h-12 text-base">
          <Link href="/teacher-signup">ثبت درخواست همکاری</Link>
        </Button>
      </div>
    );
  }

  return (
    <>
      <div className="mb-6 text-center space-y-2">
        <h1 className="text-3xl font-black text-foreground">تکمیل ثبت‌نام معلم</h1>
        <p className="text-sm text-muted-foreground leading-7">
          درخواست شما تأیید شد! یک نام کاربری و رمز عبور برای حساب معلم خود انتخاب کنید.
        </p>
      </div>

      <form
        onSubmit={handleSubmit(onSubmit)}
        className="space-y-4 bg-card/60 border border-border/80 rounded-2xl p-6 shadow-sm"
      >
        <div className="space-y-2">
          <Label htmlFor="username">نام کاربری</Label>
          <Input
            id="username"
            dir="ltr"
            disabled={isSubmitting}
            autoComplete="username"
            className={inputErrorClass(!!errors.username)}
            {...register("username")}
          />
          {errors.username && <p className="text-xs text-destructive">{errors.username.message}</p>}
        </div>

        <div className="space-y-2">
          <Label htmlFor="password">رمز عبور</Label>
          <Input
            id="password"
            type="password"
            dir="ltr"
            disabled={isSubmitting}
            autoComplete="new-password"
            className={inputErrorClass(!!errors.password)}
            {...register("password")}
          />
          {errors.password && <p className="text-xs text-destructive">{errors.password.message}</p>}
          <p className="text-xs text-muted-foreground">حداقل ۸ کاراکتر و بهتر است فقط عدد نباشد.</p>
        </div>

        <div className="space-y-2">
          <Label htmlFor="confirmPassword">تکرار رمز عبور</Label>
          <Input
            id="confirmPassword"
            type="password"
            dir="ltr"
            disabled={isSubmitting}
            autoComplete="new-password"
            className={inputErrorClass(!!errors.confirmPassword)}
            {...register("confirmPassword")}
          />
          {errors.confirmPassword && (
            <p className="text-xs text-destructive">{errors.confirmPassword.message}</p>
          )}
        </div>

        <Button type="submit" className="w-full h-12 text-base" disabled={isSubmitting}>
          {isSubmitting ? (
            <>
              <Loader2 className="ms-2 h-4 w-4 animate-spin" />
              در حال ساخت حساب…
            </>
          ) : (
            "ساخت حساب و ورود"
          )}
        </Button>
      </form>
    </>
  );
}

export default function CompleteRegistrationPage() {
  return (
    <div dir="rtl" className="flex min-h-screen flex-col items-center bg-background p-4 overflow-y-auto">
      <div className="w-full flex justify-start mb-8 sm:absolute sm:top-8 sm:start-8 sm:mb-0 sm:w-auto">
        <Link href="/" className="flex items-center gap-2 group relative">
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
          <span className="text-xl font-bold text-text-light ml-2">AI-Amooz</span>
        </Link>
      </div>

      <div className="w-full max-w-lg flex-1 flex flex-col justify-center">
        <Suspense fallback={<div className="text-center text-muted-foreground">در حال بارگذاری…</div>}>
          <CompleteRegistrationInner />
        </Suspense>
      </div>
    </div>
  );
}
