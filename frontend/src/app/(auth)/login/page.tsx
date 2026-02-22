'use client';

import React, { Suspense } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { LoginForm } from '@/components/auth/login-form';

export default function LoginPage() {
  return (
    <div dir="rtl" className="flex min-h-screen flex-col items-center bg-background p-4 overflow-y-auto">
      <div className="w-full flex justify-start mb-8 sm:absolute sm:top-8 sm:start-8 sm:mb-0 sm:w-auto">
        <Link href="/" className="flex items-center gap-2 group relative">
          <div className="relative h-12 w-16">
            <Image
              src="/logo.png"
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

      <div className="w-full max-w-md flex-1 flex flex-col justify-center">
        <Suspense fallback={<div className="h-96 flex items-center justify-center">در حال بارگذاری...</div>}>
          <LoginForm />
        </Suspense>
        <p className="mt-6 text-sm text-center text-muted-foreground">
          تازه هستید؟ <Link href="/start" className="font-semibold text-primary hover:underline">شروع رایگان</Link>
        </p>
      </div>
    </div>
  );
}
