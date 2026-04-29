"use client";

import Link from "next/link";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";

import { teacherSignupSchema, type TeacherSignupFormValues } from "@/lib/validations/auth";
import {
  ApiRequestError,
  normalizeApiError,
  persistTokens,
  persistUser,
  register as registerRequest,
} from "@/services/auth-service";

function inputErrorClass(hasError: boolean) {
  return hasError ? "border-destructive focus-visible:ring-destructive" : "";
}

export default function TeacherSignupPage() {
  const router = useRouter();

  const {
    register,
    handleSubmit,
    setError,
    setFocus,
    formState: { errors, isSubmitting },
  } = useForm<TeacherSignupFormValues>({
    resolver: zodResolver(teacherSignupSchema),
    mode: "onTouched",
    defaultValues: {
      firstName: "",
      lastName: "",
      email: "",
      phone: "",
      password: "",
      confirmPassword: "",
    },
  });

  async function onSubmit(data: TeacherSignupFormValues) {
    // پاکسازی UX: اگر شماره تلفن transform شده باشد، همین data.phone از schema خروجیِ نهایی است.
    try {
      const response = await registerRequest({
        username: data.email,
        email: data.email,
        password: data.password,
        role: "TEACHER",
        first_name: data.firstName,
        last_name: data.lastName,
        phone: data.phone,
      });

      persistTokens(response.tokens);
      persistUser(response.user);

      toast.success("حساب معلم با موفقیت ساخته شد. به پنل هدایت می‌شوید.");
      router.push("/teacher");
    } catch (err) {
      // 1) اگر خطا از API بود، سعی می‌کنیم خطاها را فیلدمحور کنیم
      if (err instanceof ApiRequestError) {
        const normalized = normalizeApiError(err);

        const fieldMap: Record<string, keyof TeacherSignupFormValues | undefined> = {
          first_name: "firstName",
          last_name: "lastName",
          email: "email",
          username: "email", // در بک‌اند ممکن است خطا روی username بیاید
          phone: "phone",
          password: "password",
          confirm_password: "confirmPassword",
          confirmPassword: "confirmPassword",
        };

        let firstFocus: keyof TeacherSignupFormValues | null = null;
        let appliedAnyFieldError = false;

        for (const [backendField, messages] of Object.entries(normalized.fieldErrors)) {
          const formField = fieldMap[backendField];

          if (!formField) continue;

          appliedAnyFieldError = true;

          const message = messages?.[0] ?? "اطلاعات وارد شده صحیح نیست";
          setError(formField, { type: "server", message });

          if (!firstFocus) firstFocus = formField;
        }

        if (firstFocus) setFocus(firstFocus);

        // اگر حداقل یکی از خطاها را روی فیلدها نشاندیم، toast را کلی نگه داریم
        if (appliedAnyFieldError) {
          toast.error("لطفاً خطاهای فرم را بررسی کنید");
          return;
        }

        // اگر خطا فیلدی نبود (مثلاً خطای کلی/اجازه دسترسی/…)
        toast.error(normalized.message);
        return;
      }

      // 2) خطاهای غیر API
      const message = err instanceof Error ? err.message : "ثبت‌نام با خطا مواجه شد";
      toast.error(message);
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
        <div className="mb-6 text-center space-y-2">
          <h1 className="text-3xl font-black text-foreground">ثبت‌نام معلم</h1>
          <p className="text-sm text-muted-foreground">اطلاعات خود را وارد کنید تا پنل معلم فعال شود.</p>
        </div>

        <form
          onSubmit={handleSubmit(onSubmit)}
          className="space-y-4 bg-card/60 border border-border/80 rounded-2xl p-6 shadow-sm"
        >
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="firstName">نام</Label>
              <Input
                id="firstName"
                disabled={isSubmitting}
                autoComplete="given-name"
                className={inputErrorClass(!!errors.firstName)}
                {...register("firstName")}
              />
              {errors.firstName && <p className="text-xs text-destructive">{errors.firstName.message}</p>}
            </div>

            <div className="space-y-2">
              <Label htmlFor="lastName">نام خانوادگی</Label>
              <Input
                id="lastName"
                disabled={isSubmitting}
                autoComplete="family-name"
                className={inputErrorClass(!!errors.lastName)}
                {...register("lastName")}
              />
              {errors.lastName && <p className="text-xs text-destructive">{errors.lastName.message}</p>}
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="email">ایمیل کاری</Label>
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

          <Separator />

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

            <p className="text-xs text-muted-foreground">
              حداقل ۸ کاراکتر و بهتر است فقط عدد نباشد.
            </p>
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
                در حال ثبت‌نام...
              </>
            ) : (
              "ایجاد حساب معلم"
            )}
          </Button>
        </form>

        <p className="mt-6 text-sm text-center text-muted-foreground">
          قبلاً حساب دارید؟{" "}
          <Link href="/login" className="font-semibold text-primary hover:underline">
            ورود
          </Link>
        </p>
      </div>
    </div>
  );
}
