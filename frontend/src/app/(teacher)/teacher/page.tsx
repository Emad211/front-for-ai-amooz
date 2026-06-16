'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useWorkspace } from '@/hooks/use-workspace';
import { OrgDashboardPage } from '@/components/teacher/org-dashboard';

export default function TeacherPage() {
  const { isOrgMode, activeWorkspace, isLoading } = useWorkspace();
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (isLoading) return;

    // Managers and org-only teachers are defaulted into org mode by the workspace
    // provider, so reaching personal mode means a real freelancer space is in use
    // → the personal analytics dashboard.
    if (!isOrgMode) {
      router.replace('/teacher/analytics');
      return;
    }

    // In org mode, only org admins/deputies (managers) get the management
    // dashboard — its API is IsOrgAdmin-only and 403s for an org teacher. Send
    // org teachers to their org-scoped classes instead.
    const orgRole = activeWorkspace?.orgRole;
    if (orgRole === 'admin' || orgRole === 'deputy') {
      setReady(true);
    } else {
      router.replace('/teacher/my-classes');
    }
  }, [isOrgMode, activeWorkspace, isLoading, router]);

  if (!ready) return null;

  return <OrgDashboardPage />;
}
