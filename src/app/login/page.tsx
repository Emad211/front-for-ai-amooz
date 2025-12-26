'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useToast } from '@/hooks/use-toast';
import { GraduationCap, Info } from 'lucide-react';
import Link from 'next/link';

const TEST_JOIN_CODE = 'AI-AMOOKHTAN';

export default function LoginPage() {
  const [joinCode, setJoinCode] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const router = useRouter();
  const { toast } = useToast();

  const handleLogin = () => {
    setIsLoading(true);

    // Simulate an API call
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
    <div className="flex min-h-screen flex-col items-center justify-center bg-background p-4">
      <div className="absolute top-8 left-8">
        <Link href="/" className="flex items-center gap-2">
            <GraduationCap className="h-7 w-7 text-primary" />
            <span className="text-xl font-bold text-text-light">AI-Amooz</span>
        </Link>
      </div>
      <div className="w-full max-w-sm text-center">
        <h1 className="text-4xl font-bold text-foreground mb-8">
            کد دعوت را وارد کنید
        </h1>
        <div className="space-y-6 text-right">
          <div className="space-y-2">
            <Label htmlFor="join-code" className="text-sm font-medium text-muted-foreground">
              کد دعوت
            </Label>
            <Input
              id="join-code"
              type="text"
              value={joinCode}
              onChange={(e) => setJoinCode(e.target.value)}
              placeholder="مثال: AI-AMOOKHTAN"
              className="h-12 bg-card border-border text-center text-lg tracking-widest"
              dir="ltr"
            />
          </div>
          <Button onClick={handleLogin} disabled={isLoading || !joinCode} className="w-full h-12 text-base bg-primary text-primary-foreground hover:bg-primary/90">
            {isLoading ? 'در حال بررسی...' : 'ادامه'}
          </Button>
        </div>

        <div className="mt-6 rounded-lg bg-card p-4 text-right">
            <h3 className="flex items-center gap-2 text-base font-bold text-foreground mb-2">
                <Info className="h-5 w-5 text-primary" />
                کد دعوت ندارید؟
            </h3>
            <p className="text-sm text-muted-foreground leading-6">
                ممکن است معلم شما یک دعوتنامه ایمیلی یا یک لینک دعوت برایتان ارسال کرده باشد. اگر هیچ‌کدام از این‌ها را ندارید، از معلم خود بپرسید.
            </p>
        </div>
      </div>
    </div>
  );
}
