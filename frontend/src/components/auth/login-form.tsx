'use client';

import React from 'react';
import Link from 'next/link';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { loginSchema, type LoginFormValues } from '@/lib/validations/auth';
import { toast } from 'sonner';
import { Loader2 } from 'lucide-react';
import { useRouter, useSearchParams } from 'next/navigation';
import { fetchMe, login as loginRequest, persistUser, persistTokens } from '@/services/auth-service';
import { OrganizationService } from '@/services/organization-service';

const GoogleIcon = (props: React.SVGProps<SVGSVGElement>) => (
    <svg role="img" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" {...props}>
        <path d="M12.48 10.92v3.28h7.84c-.24 1.84-.85 3.18-1.73 4.1-1.05 1.05-2.36 1.95-4.25 1.95-3.37 0-6.13-2.8-6.13-6.13s2.76-6.13 6.13-6.13c1.9 0 3.1.8 3.8 1.5l2.6-2.6C16.99 3.2 14.9 2 12.48 2 7.23 2 3 6.23 3 11.5s4.23 9.5 9.48 9.5c5.05 0 8.85-3.57 8.85-9.1z" />
    </svg>
);

interface LoginFormProps {
  onSwitchToJoin?: () => void;
}

export function LoginForm({ onSwitchToJoin }: LoginFormProps) {
  const [isLoading, setIsLoading] = React.useState(false);
  const router = useRouter();
  const searchParams = useSearchParams();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      username: '',
      password: '',
    },
  });

  const onSubmit = async (data: LoginFormValues) => {
    setIsLoading(true);

    try {
      const tokens = await loginRequest(data);
      persistTokens(tokens);

      const me = await fetchMe(tokens.access);
      persistUser(me);

      toast.success('ورود با موفقیت انجام شد');

      // Check if user has org admin/deputy membership for smart redirect
      let orgRedirect: string | null = null;
      try {
        const workspaces = await OrganizationService.getMyWorkspaces();
        const adminWorkspace = workspaces.find(
          (w) => w.orgRole === 'admin' || w.orgRole === 'deputy'
        );
        if (adminWorkspace) {
          orgRedirect = `/admin/organizations/${adminWorkspace.id}`;
        }
      } catch {
        // If workspace fetch fails, fall through to role-based redirect
      }

      const roleRedirectMap: Record<string, string> = {
        teacher: '/teacher',
        admin: '/admin',
        student: '/home',
      };

      const normalizedRole = me.role?.toLowerCase() ?? 'student';
      const defaultRedirect = orgRedirect ?? (roleRedirectMap[normalizedRole] ?? '/home');
      const next = searchParams.get('next');

      const isSafePath = (path: string) =>
        path.startsWith('/') && !path.startsWith('//') && !path.includes('://');

      const isAllowedByRole = (path: string) => {
        // Org admins (any platform role) can access org dashboard
        if (orgRedirect && path.startsWith('/admin/organizations/')) return true;
        if (normalizedRole === 'teacher') return path.startsWith('/teacher');
        if (normalizedRole === 'admin') return path.startsWith('/admin');
        // student
        return !path.startsWith('/teacher') && !path.startsWith('/admin');
      };

      const safeNext =
        next && isSafePath(next) && isAllowedByRole(next) ? next : defaultRedirect;

      router.push(safeNext);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'مشکلی در ورود رخ داده است';
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <>
      <h1 className="text-3xl font-bold text-foreground mb-6 text-center">
        ورود به حساب کاربری
      </h1>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        {/* دکمه ورود با گوگل */}
        <Button 
          type="button"
          variant="outline" 
          className="w-full h-12 text-base border-border bg-card"
          disabled={isLoading}
        >
          <GoogleIcon className="h-5 w-5 ms-2" />
          ورود با حساب گوگل
        </Button>

        {/* جداکننده */}
        <div className="flex items-center my-4">
          <Separator className="flex-1" />
          <span className="mx-4 text-xs text-muted-foreground">یا</span>
          <Separator className="flex-1" />
        </div>

        {/* فیلد نام کاربری */}
        <div className="space-y-2">
          <Label htmlFor="username">نام کاربری یا ایمیل</Label>
          <Input 
            id="username" 
            type="text" 
            placeholder="username@example.com" 
            className={`h-12 bg-card border-border ${errors.username ? 'border-destructive focus-visible:ring-destructive' : ''}`}
            dir="ltr"
            disabled={isLoading}
            {...register('username')}
          />
          {errors.username && (
            <p className="text-xs text-destructive mt-1">{errors.username.message}</p>
          )}
        </div>

        {/* فیلد رمز عبور */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label htmlFor="password">رمز عبور</Label>
            <Link href="#" className="text-xs text-primary hover:underline">
              فراموشی رمز عبور
            </Link>
          </div>
          <Input 
            id="password" 
            type="password" 
            placeholder="••••••••" 
            className={`h-12 bg-card border-border ${errors.password ? 'border-destructive focus-visible:ring-destructive' : ''}`}
            dir="ltr"
            disabled={isLoading}
            {...register('password')}
          />
          {errors.password && (
            <p className="text-xs text-destructive mt-1">{errors.password.message}</p>
          )}
        </div>

        <Button 
          type="submit"
          className="w-full h-12 text-base bg-primary text-primary-foreground hover:bg-primary/90"
          disabled={isLoading}
        >
          {isLoading ? (
            <>
              <Loader2 className="ms-2 h-4 w-4 animate-spin" />
              در حال بررسی...
            </>
          ) : (
            'ورود'
          )}
        </Button>
      </form>

      <div className="mt-8 space-y-3 text-center">
        <p className="text-sm text-muted-foreground">
          کد فعالسازی مدرسه یا سازمان دارید؟{' '}
          <Link href="/org-login" className="font-semibold text-primary hover:underline">
            ورود سازمانی
          </Link>
        </p>
        {onSwitchToJoin && (
          <p className="text-sm text-muted-foreground">
            حساب کاربری ندارید؟{' '}
            <button
              type="button"
              onClick={onSwitchToJoin}
              className="font-semibold text-primary hover:underline focus:outline-none"
              disabled={isLoading}
            >
              ثبت‌نام با کد دعوت
            </button>
          </p>
        )}
      </div>
    </>
  );
}
