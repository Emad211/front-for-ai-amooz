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

const TEST_JOIN_CODE = 'AI-AMOOKHTAN';

interface JoinCodeFormProps {
  onSwitchToLogin: () => void;
}

export function JoinCodeForm({ onSwitchToLogin }: JoinCodeFormProps) {
  const [isLoading, setIsLoading] = React.useState(false);
  const router = useRouter();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<JoinCodeFormValues>({
    resolver: zodResolver(joinCodeSchema),
    defaultValues: {
      code: '',
    },
  });

  const onSubmit = async (data: JoinCodeFormValues) => {
    setIsLoading(true);
    
    // شبیه‌سازی درخواست به سرور
    await new Promise((resolve) => setTimeout(resolve, 1000));
    
    if (data.code === TEST_JOIN_CODE) {
      toast.success('کد دعوت تایید شد');
      router.push('/home');
    } else {
      toast.error('کد دعوت وارد شده معتبر نیست');
      setIsLoading(false);
    }
  };

  return (
    <>
      <h1 className="text-3xl font-bold text-foreground mb-8 text-center">
        کد دعوت را وارد کنید
      </h1>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
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
              در حال بررسی...
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
    </>
  );
}
