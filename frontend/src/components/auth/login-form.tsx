'use client';

import React from 'react';
import Link from 'next/link';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { loginSchema, type LoginFormValues } from '@/lib/validations/auth';
import { toast } from 'sonner';
import { Loader2 } from 'lucide-react';
import { useRouter, useSearchParams } from 'next/navigation';
import { fetchMe, login as loginRequest, persistUser, persistTokens } from '@/services/auth-service';
import { OrganizationService } from '@/services/organization-service';
import { WORKSPACE_STORAGE_KEY } from '@/hooks/use-workspace';
import { PasswordInput } from '@/components/auth/password-input';

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

      const me = await fetchMe();
      persistUser(me);

      toast.success('ورود با موفقیت انجام شد');

      const normalizedRole = me.role?.toLowerCase() ?? 'student';

      // An org MANAGER manages an org but is NOT a platform admin (the /admin
      // route group bounces non-admins). Pre-select their org workspace so
      // /teacher opens in ORG mode (the management dashboard) rather than the
      // personal teacher area (which would 403 — a manager is not a teacher).
      if (normalizedRole === 'manager') {
        try {
          const workspaces = await OrganizationService.getMyWorkspaces();
          const orgWorkspace =
            workspaces.find((w) => w.orgRole === 'admin' || w.orgRole === 'deputy') ??
            workspaces[0];
          if (orgWorkspace) {
            localStorage.setItem(WORKSPACE_STORAGE_KEY, orgWorkspace.slug);
          }
        } catch {
          // If the workspace fetch fails, fall through to the role-based redirect.
        }
      }

      const roleRedirectMap: Record<string, string> = {
        teacher: '/teacher',
        admin: '/admin',
        manager: '/teacher', // org console (org mode pre-selected above)
        student: '/home',
      };

      const defaultRedirect = roleRedirectMap[normalizedRole] ?? '/home';
      const next = searchParams.get('next');

      const isSafePath = (path: string) =>
        path.startsWith('/') && !path.startsWith('//') && !path.includes('://');

      const isAllowedByRole = (path: string) => {
        if (normalizedRole === 'admin') return path.startsWith('/admin');
        // Teachers AND managers both live under /teacher.
        if (normalizedRole === 'teacher' || normalizedRole === 'manager')
          return path.startsWith('/teacher');
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
        {/* فیلد نام کاربری */}
        <div className="space-y-2">
          <Label htmlFor="username">نام کاربری یا ایمیل</Label>
          <Input
            id="username"
            type="text"
            placeholder="username@example.com"
            className={`h-12 bg-card border-border ${errors.username ? 'border-destructive focus-visible:ring-destructive' : ''}`}
            dir="ltr"
            autoComplete="username"
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
            <Link href="/forgot-password" className="text-xs text-primary hover:underline">
              فراموشی رمز عبور
            </Link>
          </div>
          <PasswordInput
            id="password"
            placeholder="••••••••"
            className={`h-12 bg-card border-border ${errors.password ? 'border-destructive focus-visible:ring-destructive' : ''}`}
            autoComplete="current-password"
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

    </>
  );
}
