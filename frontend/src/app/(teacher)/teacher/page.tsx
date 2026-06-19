'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useWorkspace } from '@/hooks/use-workspace';
import { OrgTeacherDashboard } from '@/components/teacher/org-teacher-dashboard';

export default function TeacherPage() {
  const { isOrgMode, isLoading } = useWorkspace();
  const router = useRouter();

  useEffect(() => {
    if (isLoading) return;
    // Personal/freelancer space → the analytics dashboard. (Managers live in the
    // dedicated /org panel, never here.)
    if (!isOrgMode) router.replace('/teacher/analytics');
  }, [isOrgMode, isLoading, router]);

  if (isLoading || !isOrgMode) return null;
  // Org workspace → the org-teacher (group-centric) dashboard.
  return <OrgTeacherDashboard />;
}
