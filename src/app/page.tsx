'use client';

import { Button } from '@/components/ui/button';
import { GraduationCap } from 'lucide-react';
import Link from 'next/link';

export default function LandingPage() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-background text-text-light p-4">
      <div className="flex items-center gap-4 mb-8">
        <GraduationCap className="h-16 w-16 text-primary" />
        <h1 className="text-5xl font-bold">AI-Amooz</h1>
      </div>
      <p className="text-xl text-text-muted mb-8 max-w-2xl text-center">
        به پلتفرم یادگیری هوشمند خوش آمدید. مسیر آموزشی خود را با کمک هوش مصنوعی شخصی‌سازی کنید.
      </p>
      <Button asChild size="lg" className="bg-primary text-primary-foreground hover:bg-primary/90">
        <Link href="/home">ورود به داشبورد</Link>
      </Button>
    </div>
  );
}
