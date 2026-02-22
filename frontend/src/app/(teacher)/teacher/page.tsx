'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useWorkspace } from '@/hooks/use-workspace';
import { OrgDashboardPage } from '@/components/teacher/org-dashboard';

export default function TeacherPage() {
  const { isOrgMode, isLoading } = useWorkspace();
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (isLoading) return;
    if (!isOrgMode) {
      router.replace('/teacher/analytics');
    } else {
      setReady(true);
    }
  }, [isOrgMode, isLoading, router]);

  if (!ready) return null;

  return <OrgDashboardPage />;
}
