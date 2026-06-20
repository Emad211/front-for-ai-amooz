'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { TeacherHeader } from "@/components/layout/teacher-header";
import { TeacherSidebar } from "@/components/layout/teacher-sidebar";
import { WorkspaceProvider } from "@/hooks/use-workspace";
import { getStoredUser } from '@/services/auth-service';
import { landingFor } from '@/lib/auth-routing';
import { OnboardingGate } from '@/components/auth/onboarding-gate';

export default function TeacherLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [allowed, setAllowed] = useState(false);

  useEffect(() => {
    // The teacher panel is for teachers (freelance + org teacher). A MANAGER goes
    // to /org, a platform ADMIN to /admin, a STUDENT to /home. An unknown/empty
    // role (stale cache before the API resolves) is allowed — API 401s handle auth.
    const role = (getStoredUser()?.role || '').toUpperCase();
    if (role && role !== 'TEACHER') {
      router.replace(landingFor(role));
      return;
    }
    setAllowed(true);
  }, [router]);

  if (!allowed) return null;

  return (
    <WorkspaceProvider>
      <OnboardingGate />
      <div className="flex min-h-screen w-full bg-background" dir="rtl">
        <div className="hidden lg:block">
          <TeacherSidebar />
        </div>
        <div className="flex-1 flex flex-col min-w-0">
          <main className="flex-1 p-3 sm:p-4 md:p-6 lg:p-8 overflow-x-hidden">
            <TeacherHeader />
            <div className="mt-6 md:mt-8">
              {children}
            </div>
          </main>
        </div>
      </div>
    </WorkspaceProvider>
  );
}
