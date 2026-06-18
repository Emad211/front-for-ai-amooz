"use client";

import { useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { CheckCircle2, GraduationCap, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import {
  teacherAccessRequestSchema,
  type TeacherAccessRequestFormValues,
} from "@/lib/validations/auth";
import { ApiRequestError, normalizeApiError } from "@/services/auth-service";
import { submitAccessRequest } from "@/services/waitlist-service";

function inputErrorClass(hasError: boolean) {
  return hasError ? "border-destructive focus-visible:ring-destructive" : "";
}

export default function TeacherSignupPage() {
  const [submitted, setSubmitted] = useState(false);

  const {
    register,
    handleSubmit,
    setError,
    setFocus,
    formState: { errors, isSubmitting },
  } = useForm<TeacherAccessRequestFormValues>({
    resolver: zodResolver(teacherAccessRequestSchema),
    mode: "onTouched",
    defaultValues: { fullName: "", phone: "", email: "", expertise: "", note: "" },
  });

  async function onSubmit(data: TeacherAccessRequestFormValues) {
    try {
      await submitAccessRequest({
        kind: "teacher",
        full_name: data.fullName,
        phone: data.phone,
        email: data.email || undefined,
        expertise: data.expertise || undefined,
        note: data.note || undefined,
      });
      setSubmitted(true);
    } catch (err) {
      if (err instanceof ApiRequestError) {
        const normalized = normalizeApiError(err);
        const fieldMap: Record<string, keyof TeacherAccessRequestFormValues | undefined> = {
          full_name: "fullName",
          phone: "phone",
          email: "email",
          expertise: "expertise",
          note: "note",
        };
        let firstFocus: keyof TeacherAccessRequestFormValues | null = null;
        let applied = false;
        for (const [backendField, messages] of Object.entries(normalized.fieldErrors)) {
          const formField = fieldMap[backendField];
          if (!formField) continue;
          applied = true;
          setError(formField, { type: "server", message: messages?.[0] ?? "مقدار نامعتبر است" });
          if (!firstFocus) firstFocus = formField;
        }
        if (firstFocus) setFocus(firstFocus);
        toast.error(applied ? "لطفاً خطاهای فرم را بررسی کنید" : normalized.message);
        return;
      }
      toast.error(err instanceof Error ? err.message : "ثبت درخواست با خطا مواجه شد");
    }
  }

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
        {submitted ? (
          <div className="bg-card/60 border border-border/80 rounded-2xl p-8 shadow-sm text-center space-y-4">
            <div className="flex justify-center">
              <div className="p-4 rounded-2xl bg-green-500/10">
                <CheckCircle2 className="h-10 w-10 text-green-500" />
              </div>
            </div>
            <h1 className="text-2xl font-black text-foreground">درخواست شما ثبت شد</h1>
            <p className="text-sm text-muted-foreground leading-7">
              تیم ما درخواست شما را بررسی می‌کند و برای تکمیل ثبت‌نام با شما تماس می‌گیرد.
              پس از تأیید، لینک ساخت حساب برایتان پیامک می‌شود.
            </p>
            <Button asChild className="w-full h-12 text-base">
              <Link href="/">بازگشت به صفحه اصلی</Link>
            </Button>
          </div>
        ) : (
          <>
            <div className="mb-6 text-center space-y-2">
              <div className="flex justify-center mb-2">
                <div className="p-3 rounded-2xl bg-primary/10">
                  <GraduationCap className="h-7 w-7 text-primary" />
                </div>
              </div>
              <h1 className="text-3xl font-black text-foreground">درخواست همکاری معلم</h1>
              <p className="text-sm text-muted-foreground leading-7">
                اطلاعات خود را ثبت کنید تا کارشناسان ما برای فعال‌سازی پنل معلم با شما تماس بگیرند.
              </p>
            </div>

            <form
              onSubmit={handleSubmit(onSubmit)}
              className="space-y-4 bg-card/60 border border-border/80 rounded-2xl p-6 shadow-sm"
            >
              <div className="space-y-2">
                <Label htmlFor="fullName">نام و نام خانوادگی</Label>
                <Input
                  id="fullName"
                  disabled={isSubmitting}
                  autoComplete="name"
                  className={inputErrorClass(!!errors.fullName)}
                  {...register("fullName")}
                />
                {errors.fullName && <p className="text-xs text-destructive">{errors.fullName.message}</p>}
              </div>

              <div className="space-y-2">
                <Label htmlFor="phone">شماره تماس</Label>
                <Input
                  id="phone"
                  type="tel"
                  dir="ltr"
                  disabled={isSubmitting}
                  autoComplete="tel"
                  placeholder="0912xxxxxxx"
                  className={inputErrorClass(!!errors.phone)}
                  {...register("phone")}
                />
                {errors.phone && <p className="text-xs text-destructive">{errors.phone.message}</p>}
              </div>

              <div className="space-y-2">
                <Label htmlFor="email">ایمیل (اختیاری)</Label>
                <Input
                  id="email"
                  type="email"
                  dir="ltr"
                  disabled={isSubmitting}
                  autoComplete="email"
                  className={inputErrorClass(!!errors.email)}
                  {...register("email")}
                />
                {errors.email && <p className="text-xs text-destructive">{errors.email.message}</p>}
              </div>

              <div className="space-y-2">
                <Label htmlFor="expertise">حوزه تدریس (اختیاری)</Label>
                <Input
                  id="expertise"
                  disabled={isSubmitting}
                  placeholder="مثلاً ریاضی، فیزیک، زبان…"
                  className={inputErrorClass(!!errors.expertise)}
                  {...register("expertise")}
                />
                {errors.expertise && <p className="text-xs text-destructive">{errors.expertise.message}</p>}
              </div>

              <div className="space-y-2">
                <Label htmlFor="note">توضیحات (اختیاری)</Label>
                <textarea
                  id="note"
                  rows={3}
                  disabled={isSubmitting}
                  className="flex w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                  {...register("note")}
                />
              </div>

              <Button type="submit" className="w-full h-12 text-base" disabled={isSubmitting}>
                {isSubmitting ? (
                  <>
                    <Loader2 className="ms-2 h-4 w-4 animate-spin" />
                    در حال ثبت…
                  </>
                ) : (
                  "ثبت درخواست"
                )}
              </Button>
            </form>

            <p className="mt-6 text-sm text-center text-muted-foreground">
              قبلاً تأیید شده‌اید و حساب دارید؟{" "}
              <Link href="/login" className="font-semibold text-primary hover:underline">
                ورود
              </Link>
            </p>
          </>
        )}
      </div>
    </div>
  );
}
