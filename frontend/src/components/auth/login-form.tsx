'use client';

import React from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';

const GoogleIcon = (props: React.SVGProps<SVGSVGElement>) => (
    <svg role="img" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" {...props}>
        <path d="M12.48 10.92v3.28h7.84c-.24 1.84-.85 3.18-1.73 4.1-1.05 1.05-2.36 1.95-4.25 1.95-3.37 0-6.13-2.8-6.13-6.13s2.76-6.13 6.13-6.13c1.9 0 3.1.8 3.8 1.5l2.6-2.6C16.99 3.2 14.9 2 12.48 2 7.23 2 3 6.23 3 11.5s4.23 9.5 9.48 9.5c5.05 0 8.85-3.57 8.85-9.1z" />
    </svg>
);

interface LoginFormProps {
  onSwitchToJoin: () => void;
}

export function LoginForm({ onSwitchToJoin }: LoginFormProps) {
  return (
    <>
      <h1 className="text-3xl font-bold text-foreground mb-6 text-center">
        ورود به حساب کاربری
      </h1>

      <div className="space-y-4">
        {/* دکمه ورود با گوگل */}
        <Button variant="outline" className="w-full h-12 text-base border-border bg-card">
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
            className="h-12 bg-card border-border"
            dir="ltr"
          />
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
            className="h-12 bg-card border-border"
            dir="ltr"
          />
        </div>

        <Button className="w-full h-12 text-base bg-primary text-primary-foreground hover:bg-primary/90">
          ورود
        </Button>
      </div>

      <p className="mt-8 text-sm text-muted-foreground text-center">
        حساب کاربری ندارید؟{' '}
        <button 
          onClick={onSwitchToJoin} 
          className="font-semibold text-primary hover:underline focus:outline-none"
        >
          ثبت‌نام با کد دعوت
        </button>
      </p>
    </>
  );
}
