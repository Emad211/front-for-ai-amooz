'use client';

import React from 'react';
import { useRouter } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { joinCodeSchema, type JoinCodeFormValues } from '@/lib/validations/auth';
import { toast } from 'sonner';
import { Loader2, Info } from 'lucide-react';
import { ApiRequestError, inviteLogin, persistTokens, persistUser } from '@/services/auth-service';

const RAW_API_URL = (process.env.NEXT_PUBLIC_API_URL ?? '').replace(/\/$/, '');
const API_URL = RAW_API_URL.endsWith('/api') ? RAW_API_URL : `${RAW_API_URL}/api`;

interface JoinCodeFormProps {
  onSwitchToLogin?: () => void;
}

export function JoinCodeForm({ onSwitchToLogin }: JoinCodeFormProps) {
  const [isLoading, setIsLoading] = React.useState(false);
  const [submitError, setSubmitError] = React.useState<string | null>(null);
  const router = useRouter();

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<JoinCodeFormValues>({
    resolver: zodResolver(joinCodeSchema),
    defaultValues: {
      code: '',
      phone: '',
    },
  });

  const onSubmit = async (data: JoinCodeFormValues) => {
    setIsLoading(true);
    setSubmitError(null);

    try {
      if (!RAW_API_URL) {
        throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
      }

      const resp = await inviteLogin({ code: data.code, phone: data.phone });
      persistTokens(resp.tokens);
      persistUser(resp.user);

      toast.success('ورود با کد دعوت انجام شد');
      router.push('/home');
    } catch (err) {
      console.error(err);

      if (err instanceof ApiRequestError && err.payload && typeof err.payload === 'object') {
        const payloadObj = err.payload as Record<string, unknown>;
        const errorsObj = payloadObj.errors;
        if (errorsObj && typeof errorsObj === 'object') {
          const fieldErrors = errorsObj as Record<string, unknown>;
          const phoneMsgs = fieldErrors.phone;
          const codeMsgs = fieldErrors.code;
          if (Array.isArray(phoneMsgs) && phoneMsgs.length) {
            setError('phone', { type: 'server', message: String(phoneMsgs[0]) });
          }
          if (Array.isArray(codeMsgs) && codeMsgs.length) {
            setError('code', { type: 'server', message: String(codeMsgs[0]) });
          }
        }
      }

      const message = err instanceof Error ? err.message : 'خطا در ورود با کد دعوت';
      setSubmitError(message);
      toast.error(message);
      setIsLoading(false);
    }
  };

  return (
    <>
      <h1 className="text-3xl font-bold text-foreground mb-8 text-center">
        کد دعوت را وارد کنید
      </h1>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        {submitError && (
          <div className="rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
            {submitError}
          </div>
        )}

        <div className="space-y-2">
          <Label htmlFor="phone" className="text-sm font-medium text-muted-foreground">
            شماره تماس
          </Label>
          <Input
            id="phone"
            type="tel"
            className={`h-12 bg-card border-border text-center text-lg tracking-widest ${errors.phone ? 'border-destructive focus-visible:ring-destructive' : ''}`}
            dir="ltr"
            placeholder="09123456789"
            disabled={isLoading}
            {...register('phone')}
          />
          {errors.phone && (
            <p className="text-xs text-destructive mt-1 text-center">{errors.phone.message}</p>
          )}
        </div>

        <div className="space-y-2">
          <Label htmlFor="code" className="text-sm font-medium text-muted-foreground">
            کد دعوت
          </Label>
          <Input
            id="code"
            type="text"
            className={`h-12 bg-card border-border text-center text-lg tracking-widest ${errors.code ? 'border-destructive focus-visible:ring-destructive' : ''}`}
            dir="ltr"
            disabled={isLoading}
            {...register('code')}
          />
          {errors.code && (
            <p className="text-xs text-destructive mt-1 text-center">{errors.code.message}</p>
          )}
        </div>

        <Button 
          type="submit"
          disabled={isLoading} 
          className="w-full h-12 text-base bg-primary text-primary-foreground hover:bg-primary/90"
        >
          {isLoading ? (
            <>
              <Loader2 className="ms-2 h-4 w-4 animate-spin" />
              در حال ورود...
            </>
          ) : (
            'ادامه'
          )}
        </Button>
      </form>

      {/* باکس اطلاعات */}
      <div className="mt-6 rounded-lg bg-card p-4">
        <h3 className="flex items-center gap-2 text-base font-bold text-foreground mb-2">
          <Info className="h-5 w-5 text-primary" />
          کد دعوت ندارید؟
        </h3>
        <p className="text-sm text-muted-foreground leading-7">
          ممکن است معلم شما یک دعوتنامه ایمیلی یا یک لینک دعوت برایتان ارسال کرده باشد. 
          اگر هیچ‌کدام از این‌ها را ندارید، از معلم خود بپرسید.
        </p>
      </div>

      {onSwitchToLogin && (
        <p className="mt-8 text-sm text-muted-foreground text-center">
          حساب کاربری دارید؟{' '}
          <button 
            type="button"
            onClick={onSwitchToLogin} 
            className="font-semibold text-primary hover:underline focus:outline-none"
            disabled={isLoading}
          >
            ورود
          </button>
        </p>
      )}
    </>
  );
}
