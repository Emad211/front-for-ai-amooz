"use client";

import { useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Building2, CheckCircle2, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import {
  orgAccessRequestSchema,
  type OrgAccessRequestFormValues,
} from "@/lib/validations/auth";
import { ApiRequestError, normalizeApiError } from "@/services/auth-service";
import { submitAccessRequest } from "@/services/waitlist-service";

function inputErrorClass(hasError: boolean) {
  return hasError ? "border-destructive focus-visible:ring-destructive" : "";
}

export default function OrganizationSignupPage() {
  const [submitted, setSubmitted] = useState(false);

  const {
    register,
    handleSubmit,
    setError,
    setFocus,
    formState: { errors, isSubmitting },
  } = useForm<OrgAccessRequestFormValues>({
    resolver: zodResolver(orgAccessRequestSchema),
    mode: "onTouched",
    defaultValues: {
      fullName: "",
      orgName: "",
      phone: "",
      email: "",
      city: "",
      expectedStudents: "",
      website: "",
      note: "",
    },
  });

  async function onSubmit(data: OrgAccessRequestFormValues) {
    try {
      await submitAccessRequest({
        kind: "organization",
        full_name: data.fullName,
        org_name: data.orgName,
        phone: data.phone,
        email: data.email || undefined,
        city: data.city || undefined,
        expected_students: data.expectedStudents ? Number(data.expectedStudents) : undefined,
        website: data.website || undefined,
        note: data.note || undefined,
      });
      setSubmitted(true);
    } catch (err) {
      if (err instanceof ApiRequestError) {
        const normalized = normalizeApiError(err);
        const fieldMap: Record<string, keyof OrgAccessRequestFormValues | undefined> = {
          full_name: "fullName",
          org_name: "orgName",
          phone: "phone",
          email: "email",
          city: "city",
          expected_students: "expectedStudents",
          website: "website",
          note: "note",
        };
        let firstFocus: keyof OrgAccessRequestFormValues | null = null;
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
            <h1 className="text-2xl font-black text-foreground">درخواست سازمان شما ثبت شد</h1>
            <p className="text-sm text-muted-foreground leading-7">
              کارشناسان ما درخواست سازمان شما را بررسی و برای راه‌اندازی با شما تماس می‌گیرند.
              پس از تأیید، کد فعال‌سازی مدیر سازمان برایتان پیامک می‌شود.
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
                  <Building2 className="h-7 w-7 text-primary" />
                </div>
              </div>
              <h1 className="text-3xl font-black text-foreground">درخواست همکاری سازمان</h1>
              <p className="text-sm text-muted-foreground leading-7">
                مدرسه یا مؤسسه آموزشی خود را معرفی کنید تا تیم ما برای راه‌اندازی با شما تماس بگیرد.
              </p>
            </div>

            <form
              onSubmit={handleSubmit(onSubmit)}
              className="space-y-4 bg-card/60 border border-border/80 rounded-2xl p-6 shadow-sm"
            >
              <div className="space-y-2">
                <Label htmlFor="orgName">نام سازمان / مدرسه</Label>
                <Input
                  id="orgName"
                  disabled={isSubmitting}
                  className={inputErrorClass(!!errors.orgName)}
                  {...register("orgName")}
                />
                {errors.orgName && <p className="text-xs text-destructive">{errors.orgName.message}</p>}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="fullName">نام رابط</Label>
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
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
                  <Label htmlFor="city">شهر (اختیاری)</Label>
                  <Input
                    id="city"
                    disabled={isSubmitting}
                    className={inputErrorClass(!!errors.city)}
                    {...register("city")}
                  />
                  {errors.city && <p className="text-xs text-destructive">{errors.city.message}</p>}
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="expectedStudents">تعداد تقریبی دانش‌آموز (اختیاری)</Label>
                  <Input
                    id="expectedStudents"
                    type="number"
                    inputMode="numeric"
                    dir="ltr"
                    disabled={isSubmitting}
                    className={inputErrorClass(!!errors.expectedStudents)}
                    {...register("expectedStudents")}
                  />
                  {errors.expectedStudents && (
                    <p className="text-xs text-destructive">{errors.expectedStudents.message}</p>
                  )}
                </div>
                <div className="space-y-2">
                  <Label htmlFor="website">وب‌سایت (اختیاری)</Label>
                  <Input
                    id="website"
                    type="url"
                    dir="ltr"
                    disabled={isSubmitting}
                    placeholder="https://"
                    className={inputErrorClass(!!errors.website)}
                    {...register("website")}
                  />
                  {errors.website && <p className="text-xs text-destructive">{errors.website.message}</p>}
                </div>
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
                  "ثبت درخواست سازمان"
                )}
              </Button>
            </form>

            <p className="mt-6 text-sm text-center text-muted-foreground">
              کد فعال‌سازی سازمان دارید؟{" "}
              <Link href="/org-login" className="font-semibold text-primary hover:underline">
                ورود سازمانی
              </Link>
            </p>
          </>
        )}
      </div>
    </div>
  );
}
