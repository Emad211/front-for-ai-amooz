'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { TeacherHeader } from '@/components/layout/teacher-header';
import { TeacherSidebar } from '@/components/layout/teacher-sidebar';
import { WorkspaceProvider, useWorkspace } from '@/hooks/use-workspace';
import { getStoredUser } from '@/services/auth-service';
import { landingFor } from '@/lib/auth-routing';
import { OnboardingGate } from '@/components/auth/onboarding-gate';

/**
 * Org-MANAGER panel guard. Allowed for a platform MANAGER, or anyone who admins
 * at least one org (a teacher who is also an org admin/deputy). Everyone else is
 * bounced to their own dashboard. Lives inside WorkspaceProvider so it can read
 * the user's memberships.
 */
function OrgGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { workspaces, isLoading } = useWorkspace();
  const [allowed, setAllowed] = useState(false);

  useEffect(() => {
    if (isLoading) return;
    const role = (getStoredUser()?.role || '').toUpperCase();
    const managesAnOrg = workspaces.some(
      (w) => w.orgRole === 'admin' || w.orgRole === 'deputy',
    );
    if (role === 'MANAGER' || managesAnOrg) {
      setAllowed(true);
    } else {
      router.replace(landingFor(getStoredUser()?.role));
    }
  }, [isLoading, workspaces, router]);

  if (!allowed) return null;
  return <>{children}</>;
}

export default function OrgLayout({ children }: { children: React.ReactNode }) {
  return (
    <WorkspaceProvider>
      <OnboardingGate />
      <OrgGuard>
        <div className="flex min-h-screen w-full bg-background" dir="rtl">
          <div className="hidden lg:block">
            <TeacherSidebar />
          </div>
          <div className="flex-1 flex flex-col min-w-0">
            <main className="flex-1 p-3 sm:p-4 md:p-6 lg:p-8 overflow-x-hidden">
              <TeacherHeader />
              <div className="mt-6 md:mt-8">{children}</div>
            </main>
          </div>
        </div>
      </OrgGuard>
    </WorkspaceProvider>
  );
}
