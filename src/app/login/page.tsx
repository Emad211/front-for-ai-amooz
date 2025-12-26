'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useToast } from '@/hooks/use-toast';
import { GraduationCap, Info } from 'lucide-react';
import Link from 'next/link';
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Separator } from '@/components/ui/separator';

const GoogleIcon = (props) => (
    <svg role="img" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" {...props}>
        <path d="M12.48 10.92v3.28h7.84c-.24 1.84-.85 3.18-1.73 4.1-1.05 1.05-2.36 1.95-4.25 1.95-3.37 0-6.13-2.8-6.13-6.13s2.76-6.13 6.13-6.13c1.9 0 3.1.8 3.8 1.5l2.6-2.6C16.99 3.2 14.9 2 12.48 2 7.23 2 3 6.23 3 11.5s4.23 9.5 9.48 9.5c5.05 0 8.85-3.57 8.85-9.1z" />
    </svg>
);


const TEST_JOIN_CODE = 'AI-AMOOKHTAN';

export default function LoginPage() {
  const [joinCode, setJoinCode] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('join-code');
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
      <div className="absolute top-8 right-8">
        <Link href="/" className="flex items-center gap-2">
            <GraduationCap className="h-7 w-7 text-primary" />
            <span className="text-xl font-bold text-text-light">AI-Amooz</span>
        </Link>
      </div>
      <div className="w-full max-w-md text-center">
         <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
            <TabsList className="grid w-full grid-cols-2 bg-card border-border mb-8">
                <TabsTrigger value="join-code" className="text-base">کد دعوت</TabsTrigger>
                <TabsTrigger value="login" className="text-base">ورود</TabsTrigger>
            </TabsList>
            <TabsContent value="join-code">
                 <h1 className="text-3xl font-bold text-foreground mb-8">
                    به AI-Amooz خوش آمدید
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
                    <h3 className="flex items-center justify-end gap-2 text-base font-bold text-foreground mb-2">
                        کد دعوت ندارید؟
                        <Info className="h-5 w-5 text-primary" />
                    </h3>
                    <p className="text-sm text-muted-foreground leading-6">
                        ممکن است معلم شما یک دعوتنامه ایمیلی یا یک لینک دعوت برایتان ارسال کرده باشد. اگر هیچ‌کدام از این‌ها را ندارید، از معلم خود بپرسید.
                    </p>
                </div>
                <p className="mt-8 text-sm text-muted-foreground">
                  حساب کاربری دارید؟{' '}
                  <button onClick={() => setActiveTab('login')} className="font-semibold text-primary hover:underline focus:outline-none">
                    ورود
                  </button>
                </p>
            </TabsContent>
             <TabsContent value="login">
                <h1 className="text-3xl font-bold text-foreground mb-6">
                    ورود به حساب کاربری
                </h1>
                <div className="space-y-4 text-right">
                    <Button variant="outline" className="w-full h-12 text-base border-border bg-card">
                         <GoogleIcon className="h-5 w-5 ml-2" />
                        ورود با حساب گوگل
                    </Button>
                    
                    <div className="flex items-center my-4">
                        <Separator className="flex-1" />
                        <span className="mx-4 text-xs text-muted-foreground">یا</span>
                        <Separator className="flex-1" />
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="username">نام کاربری یا ایمیل</Label>
                        <Input id="username" type="text" placeholder="username@example.com" className="h-12 bg-card border-border" />
                    </div>

                    <div className="space-y-2">
                         <div className="flex items-center justify-between">
                            <Label htmlFor="password">رمز عبور</Label>
                            <Link href="#" className="text-xs text-primary hover:underline">
                                فراموشی رمز عبور
                            </Link>
                        </div>
                        <Input id="password" type="password" placeholder="••••••••" className="h-12 bg-card border-border" />
                    </div>

                    <Button className="w-full h-12 text-base bg-primary text-primary-foreground hover:bg-primary/90">
                        ورود
                    </Button>
                </div>
            </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
