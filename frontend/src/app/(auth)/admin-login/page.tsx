'use client';

import { useState } from 'react';
import { Shield, Eye, EyeOff, Mail, Lock, Chrome, Loader2 } from 'lucide-react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import Image from 'next/image';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { toast } from 'sonner';
import { login, fetchMe, persistTokens, persistUser } from '@/services/auth-service';

export default function AdminLoginPage() {
  const router = useRouter();
  const [showPassword, setShowPassword] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    
    try {
      // Step 1: Login to get tokens
      // Admin might use email but the login API expects 'username'
      const tokens = await login({ username: email, password, role: 'ADMIN' });
      persistTokens(tokens);

      // Step 2: Fetch user info
      const user = await fetchMe(tokens.access);

      // Step 3: Check role
      const hasAdminAccess =
        user.role.toLowerCase() === 'admin' || Boolean(user.is_staff) || Boolean(user.is_superuser);

      if (!hasAdminAccess) {
        toast.error('شما دسترسی مدیریت ندارید.');
        return;
      }

      const adminUser = user.role.toLowerCase() === 'admin' ? user : { ...user, role: 'ADMIN' };
      persistUser(adminUser);
      toast.success('خوش آمدید، مدیر!');
      
      // Step 4: Redirect to admin panel
      router.push('/admin');
    } catch (error: any) {
      console.error('Admin login error:', error);
      toast.error(error.message || 'خطا در ورود به پنل مدیریت');
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoogleLogin = () => {
    // Handle Google login
    console.log('Google admin login');
  };

  return (
    <div dir="rtl" className="min-h-screen bg-gradient-to-br from-primary/5 via-background to-primary/10 flex flex-col items-center p-4 overflow-y-auto">
      {/* Background Effects */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 right-0 w-72 h-72 bg-primary/10 rounded-full blur-3xl"></div>
        <div className="absolute bottom-0 left-0 w-96 h-96 bg-primary/5 rounded-full blur-3xl"></div>
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-primary/3 rounded-full blur-[100px]"></div>
      </div>

      {/* Back to Landing */}
      <div className="w-full flex justify-end mb-8 z-10">
        <Link 
          href="/" 
          className="text-muted-foreground hover:text-primary transition-colors"
        >
          ← برگشت به صفحه اصلی
        </Link>
      </div>

      {/* Main Card */}
      <div className="flex-1 flex items-center justify-center w-full z-10">
        <Card className="w-full max-w-md bg-card/80 backdrop-blur-xl border-border/50 shadow-2xl">
        <CardHeader className="space-y-6 text-center pb-8">
          {/* Logo */}
          <div className="flex justify-center">
            <div className="relative p-4 rounded-2xl bg-primary/10">
              <div className="relative h-16 w-20">
                <Image
                  src="/logo.png"
                  alt="AI-Amooz logo"
                  fill
                  sizes="80px"
                  className="object-contain scale-[2.2] origin-center"
                  priority
                />
              </div>
            </div>
          </div>
          
          {/* Title */}
          <div className="space-y-2">
            <div className="flex items-center justify-center gap-2 mb-2">
              <Shield className="w-6 h-6 text-primary" />
              <h1 className="text-2xl font-bold text-foreground">پنل مدیریت</h1>
            </div>
            <p className="text-muted-foreground text-sm">
              ورود به پنل مدیریت AI-Amooz
            </p>
          </div>
        </CardHeader>

        <CardContent className="space-y-6">
          {/* Google Login */}
          <Button
            onClick={handleGoogleLogin}
            variant="outline"
            className="w-full h-12 text-base border-border/50 hover:bg-card/50 hover:border-primary/30 transition-all"
          >
            <Chrome className="w-5 h-5 ml-3" />
            ورود با حساب گوگل
          </Button>

          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <Separator className="bg-border/50" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-card px-4 text-muted-foreground">یا</span>
            </div>
          </div>

          {/* Login Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Email Field */}
            <div className="space-y-2">
              <Label htmlFor="email" className="text-sm font-medium text-foreground">
                ایمیل
              </Label>
              <div className="relative">
                <Mail className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  id="email"
                  type="email"
                  placeholder="admin@ai-amooz.ir"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="pr-10 h-12 bg-background/50 border-border/50 focus:border-primary focus:bg-background/80 transition-all"
                  required
                />
              </div>
            </div>

            {/* Password Field */}
            <div className="space-y-2">
              <Label htmlFor="password" className="text-sm font-medium text-foreground">
                رمز عبور
              </Label>
              <div className="relative">
                <Lock className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="pr-10 pl-10 h-12 bg-background/50 border-border/50 focus:border-primary focus:bg-background/80 transition-all"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {/* Login Button */}
            <Button 
              type="submit" 
              disabled={isLoading}
              className="w-full h-12 text-base bg-primary hover:bg-primary/90 shadow-lg shadow-primary/20 transition-all hover:scale-[1.02]"
            >
              {isLoading ? (
                <>
                  <Loader2 className="ml-2 h-4 w-4 animate-spin" />
                  در حال بررسی...
                </>
              ) : (
                'ورود به پنل مدیریت'
              )}
            </Button>
          </form>

          {/* Footer Links */}
          <div className="text-center space-y-2 pt-4 border-t border-border/30">
            <Link 
              href="#" 
              className="text-sm text-muted-foreground hover:text-primary transition-colors block"
            >
              رمز عبور را فراموش کرده‌اید؟
            </Link>
            <p className="text-xs text-muted-foreground">
              برای دسترسی به پنل مدیریت، احراز هویت الزامی است
            </p>
          </div>
        </CardContent>
      </Card>
    </div>

    {/* Security Notice */}
    <div className="absolute bottom-8 left-8 right-8 text-center z-10">
      <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-card/60 backdrop-blur-sm border border-border/30 text-xs text-muted-foreground">
        <Shield className="w-3 h-3" />
        اتصال امن و رمزگذاری شده
      </div>
    </div>
  </div>
);
}