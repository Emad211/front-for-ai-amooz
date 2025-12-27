'use client';

import { useState } from 'react';
import { GraduationCap } from 'lucide-react';
import Link from 'next/link';
import Image from 'next/image';
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { JoinCodeForm } from '@/components/auth/join-code-form';
import { LoginForm } from '@/components/auth/login-form';

export default function LoginPage() {
  const [activeTab, setActiveTab] = useState('join-code');

  return (
    <div dir="rtl" className="flex min-h-screen flex-col items-center justify-center bg-background p-4">
      {/* لوگو - موقعیت بالا چپ برای RTL */}
      <div className="absolute top-8 start-8">
        <Link href="/" className="flex items-center gap-2 group relative">
          <div className="relative h-12 w-16">
            <Image
              src="/logo (2).png"
              alt="AI-Amooz logo"
              fill
              sizes="128px"
              className="object-contain transition-all duration-300 invert dark:invert-0 dark:mix-blend-screen dark:brightness-125 scale-[2.2] origin-center"
              priority
            />
          </div>
          <span className="text-xl font-bold text-text-light ml-2">AI-Amooz</span>
        </Link>
      </div>

      <div className="w-full max-w-md">
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full" dir="rtl">
          <TabsList className="grid w-full grid-cols-2 bg-card border-border mb-8">
            <TabsTrigger value="join-code" className="text-base">کد دعوت</TabsTrigger>
            <TabsTrigger value="login" className="text-base">ورود</TabsTrigger>
          </TabsList>

          {/* تب کد دعوت */}
          <TabsContent value="join-code">
            <JoinCodeForm onSwitchToLogin={() => setActiveTab('login')} />
          </TabsContent>

          {/* تب ورود */}
          <TabsContent value="login">
            <LoginForm onSwitchToJoin={() => setActiveTab('join-code')} />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
