'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useToast } from '@/hooks/use-toast';
import { Info } from 'lucide-react';

const TEST_JOIN_CODE = 'AI-AMOOKHTAN';

interface JoinCodeFormProps {
  onSwitchToLogin: () => void;
}

export function JoinCodeForm({ onSwitchToLogin }: JoinCodeFormProps) {
  const [joinCode, setJoinCode] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const router = useRouter();
  const { toast } = useToast();

  const handleJoin = () => {
    setIsLoading(true);

    setTimeout(() => {
      if (joinCode === TEST_JOIN_CODE) {
        router.push('/home');
      } else {
        toast({
          variant: 'destructive',
          title: 'خطا',
          description: 'کد دعوت وارد شده معتبر نیست.',
        });
        setIsLoading(false);
      }
    }, 1000);
  };

  return (
    <>
      <h1 className="text-3xl font-bold text-foreground mb-8">
        کد دعوت را وارد کنید
      </h1>

      <div className="space-y-6">
        <div className="space-y-2">
          <Label htmlFor="join-code" className="text-sm font-medium text-muted-foreground">
            کد دعوت
          </Label>
          <Input
            id="join-code"
            type="text"
            value={joinCode}
            onChange={(e) => setJoinCode(e.target.value)}
            className="h-12 bg-card border-border text-center text-lg tracking-widest"
            dir="ltr"
          />
        </div>

        <Button 
          onClick={handleJoin} 
          disabled={isLoading || !joinCode} 
          className="w-full h-12 text-base bg-primary text-primary-foreground hover:bg-primary/90"
        >
          {isLoading ? 'در حال بررسی...' : 'ادامه'}
        </Button>
      </div>

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
          onClick={onSwitchToLogin} 
          className="font-semibold text-primary hover:underline focus:outline-none"
        >
          ورود
        </button>
      </p>
    </>
  );
}
