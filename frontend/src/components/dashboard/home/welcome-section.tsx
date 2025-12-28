'use client';

import { UserProfile } from '@/constants/mock/user-data';

interface WelcomeSectionProps {
  profile: UserProfile | null;
}

export function WelcomeSection({ profile }: WelcomeSectionProps) {
  const firstName = profile?.name.split(' ')[0] || 'کاربر';
  
  return (
    <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
      <div className="text-right">
        <h1 className="text-2xl md:text-3xl font-black text-foreground">داشبورد من</h1>
        <p className="text-sm md:text-base text-muted-foreground mt-1 font-medium">
          خوش آمدی {firstName}! بیا امروز هم چیزهای جدید یاد بگیریم.
        </p>
      </div>
      <div className="hidden md:block text-sm font-bold text-muted-foreground bg-muted/50 px-4 py-2 rounded-xl border border-border/50">
        امروز: {new Date().toLocaleDateString('fa-IR', { year: 'numeric', month: 'long', day: 'numeric' })}
      </div>
    </div>
  );
}
