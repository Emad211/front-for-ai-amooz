'use client';

import { useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { useRouter } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { teacherSignupSchema, type TeacherSignupFormValues } from '@/lib/validations/auth';
import { toast } from 'sonner';
import { Loader2 } from 'lucide-react';

export default function TeacherSignupPage() {
  const router = useRouter();
  const { register, handleSubmit, formState: { errors } } = useForm<TeacherSignupFormValues>({
    resolver: zodResolver(teacherSignupSchema),
    defaultValues: {
      fullName: '',
      email: '',
      phone: '',
      password: '',
      confirmPassword: '',
    },
  });

  const [isLoading, setIsLoading] = useState(false);

  async function onSubmit(data: TeacherSignupFormValues) {
    setIsLoading(true);
    await new Promise((resolve) => setTimeout(resolve, 1200));
    toast.success('حساب معلم با موفقیت ساخته شد. اکنون وارد شوید.');
    router.push('/login');
  }

  return (
    <div dir="rtl" className="flex min-h-screen flex-col items-center bg-background p-4 overflow-y-auto">
      <div className="w-full flex justify-start mb-8 sm:absolute sm:top-8 sm:start-8 sm:mb-0 sm:w-auto">
        <Link href="/" className="flex items-center gap-2 group relative">
          <div className="relative h-12 w-16">
            <Image
              src="/logo (2).png"
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

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 bg-card/60 border border-border/80 rounded-2xl p-6 shadow-sm">
          <div className="space-y-2">
            <Label htmlFor="fullName">نام و نام خانوادگی</Label>
            <Input id="fullName" disabled={isLoading} {...register('fullName')} />
            {errors.fullName && <p className="text-xs text-destructive">{errors.fullName.message}</p>}
          </div>

          <div className="space-y-2">
            <Label htmlFor="email">ایمیل کاری</Label>
            <Input id="email" type="email" dir="ltr" disabled={isLoading} {...register('email')} />
            {errors.email && <p className="text-xs text-destructive">{errors.email.message}</p>}
          </div>

          <div className="space-y-2">
            <Label htmlFor="phone">شماره تماس</Label>
            <Input id="phone" type="tel" dir="ltr" disabled={isLoading} {...register('phone')} />
            {errors.phone && <p className="text-xs text-destructive">{errors.phone.message}</p>}
          </div>

          <Separator />

          <div className="space-y-2">
            <Label htmlFor="password">رمز عبور</Label>
            <Input id="password" type="password" dir="ltr" disabled={isLoading} {...register('password')} />
            {errors.password && <p className="text-xs text-destructive">{errors.password.message}</p>}
          </div>

          <div className="space-y-2">
            <Label htmlFor="confirmPassword">تکرار رمز عبور</Label>
            <Input id="confirmPassword" type="password" dir="ltr" disabled={isLoading} {...register('confirmPassword')} />
            {errors.confirmPassword && <p className="text-xs text-destructive">{errors.confirmPassword.message}</p>}
          </div>

          <Button type="submit" className="w-full h-12 text-base" disabled={isLoading}>
            {isLoading ? (
              <>
                <Loader2 className="ms-2 h-4 w-4 animate-spin" />
                در حال ثبت‌نام...
              </>
            ) : 'ایجاد حساب معلم'}
          </Button>
        </form>

        <p className="mt-6 text-sm text-center text-muted-foreground">
          قبلاً حساب دارید؟ <Link href="/login" className="font-semibold text-primary hover:underline">ورود</Link>
        </p>
      </div>
    </div>
  );
}
