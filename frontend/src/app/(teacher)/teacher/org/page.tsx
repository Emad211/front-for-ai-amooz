'use client';

import { useWorkspace } from '@/hooks/use-workspace';
import { OrgManagementPanel } from '@/components/organization/org-management-panel';
import { Skeleton } from '@/components/ui/skeleton';
import { Building2 } from 'lucide-react';

/**
 * Org manager console: manage members + invitation codes for the active org.
 * Only org admins/deputies (managers) reach this from the nav; the backend
 * enforces IsOrgAdmin, and we guard the active workspace's org role here too.
 */
export default function OrgManagePage() {
  const { activeWorkspace, isOrgMode, isLoading } = useWorkspace();

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-56" />
        <Skeleton className="h-96 rounded-2xl" />
      </div>
    );
  }

  const isOrgManager =
    isOrgMode &&
    (activeWorkspace?.orgRole === 'admin' || activeWorkspace?.orgRole === 'deputy');

  if (!isOrgManager || !activeWorkspace) {
    return (
      <p className="text-muted-foreground text-center py-12">
        برای مدیریت اعضا و کدهای دعوت، از سوییچر بالا سازمانی که مدیرش هستید را انتخاب کنید.
      </p>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        {activeWorkspace.logo ? (
          <img
            src={activeWorkspace.logo}
            alt={activeWorkspace.name}
            className="h-10 w-10 rounded-xl object-cover"
          />
        ) : (
          <div className="h-10 w-10 rounded-xl bg-primary/10 flex items-center justify-center">
            <Building2 className="h-5 w-5 text-primary" />
          </div>
        )}
        <div>
          <h1 className="text-2xl font-black text-foreground">مدیریت سازمان</h1>
          <p className="text-sm text-muted-foreground">{activeWorkspace.name} — اعضا و کدهای دعوت</p>
        </div>
      </div>

      <OrgManagementPanel orgId={activeWorkspace.id} />
    </div>
  );
}
