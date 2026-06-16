'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useWorkspace } from '@/hooks/use-workspace';
import { OrgDashboardPage } from '@/components/teacher/org-dashboard';
import { OrgTeacherDashboard } from '@/components/teacher/org-teacher-dashboard';

type TeacherView = 'pending' | 'manager' | 'org-teacher';

export default function TeacherPage() {
  const { isOrgMode, activeWorkspace, isLoading } = useWorkspace();
  const router = useRouter();
  const [view, setView] = useState<TeacherView>('pending');

  useEffect(() => {
    if (isLoading) return;

    // Managers and org-only teachers are defaulted into org mode by the workspace
    // provider, so reaching personal mode means a real freelancer space is in use
    // → the personal analytics dashboard.
    if (!isOrgMode) {
      router.replace('/teacher/analytics');
      return;
    }

    // In org mode: org admins/deputies (managers) get the management dashboard;
    // org teachers get their group-centric dashboard (their study groups).
    const orgRole = activeWorkspace?.orgRole;
    setView(orgRole === 'admin' || orgRole === 'deputy' ? 'manager' : 'org-teacher');
  }, [isOrgMode, activeWorkspace, isLoading, router]);

  if (view === 'manager') return <OrgDashboardPage />;
  if (view === 'org-teacher') return <OrgTeacherDashboard />;
  return null;
}
