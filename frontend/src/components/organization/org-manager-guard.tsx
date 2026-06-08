'use client';

import { type ReactNode } from 'react';
import Link from 'next/link';
import { ShieldAlert, Building2 } from 'lucide-react';
import { useWorkspace } from '@/hooks/use-workspace';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';

function GuardSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-8 w-56" />
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-28 rounded-2xl" />
        ))}
      </div>
    </div>
  );
}

function NotAllowed({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="flex flex-col items-center justify-center text-center gap-4 py-16">
      <div className="h-16 w-16 rounded-2xl bg-destructive/10 flex items-center justify-center">
        <ShieldAlert className="h-8 w-8 text-destructive" />
      </div>
      <div>
        <h2 className="text-xl font-bold text-foreground">{title}</h2>
        <p className="text-sm text-muted-foreground mt-1 max-w-md">{hint}</p>
      </div>
      <Button asChild variant="outline">
        <Link href="/teacher">بازگشت به داشبورد</Link>
      </Button>
    </div>
  );
}

function NeedsOrg() {
  return (
    <div className="flex flex-col items-center justify-center text-center gap-4 py-16">
      <div className="h-16 w-16 rounded-2xl bg-primary/10 flex items-center justify-center">
        <Building2 className="h-8 w-8 text-primary" />
      </div>
      <div>
        <h2 className="text-xl font-bold text-foreground">یک فضای سازمانی انتخاب کنید</h2>
        <p className="text-sm text-muted-foreground mt-1 max-w-md">
          این بخش مخصوص فضای سازمان است. از سوییچر بالای صفحه، سازمان خود را انتخاب کنید.
        </p>
      </div>
    </div>
  );
}

/**
 * Gate org-**management** pages: requires org mode + orgRole admin/deputy.
 * Plain org teachers and personal-mode users are politely blocked.
 */
export function OrgManagerGuard({ children }: { children: ReactNode }) {
  const { isOrgMode, activeWorkspace, isLoading } = useWorkspace();

  if (isLoading) return <GuardSkeleton />;
  if (!isOrgMode || !activeWorkspace) return <NeedsOrg />;

  const role = activeWorkspace.orgRole;
  if (role !== 'admin' && role !== 'deputy') {
    return (
      <NotAllowed
        title="دسترسی مدیریتی ندارید"
        hint="این بخش مخصوص مدیران سازمان است. برای دسترسی با مدیر سازمان خود هماهنگ کنید."
      />
    );
  }

  return <>{children}</>;
}

/**
 * Gate org-mode pages available to ANY org member (e.g. a teacher's own
 * study groups). Only requires being inside an org workspace.
 */
export function OrgModeGuard({ children }: { children: ReactNode }) {
  const { isOrgMode, activeWorkspace, isLoading } = useWorkspace();

  if (isLoading) return <GuardSkeleton />;
  if (!isOrgMode || !activeWorkspace) return <NeedsOrg />;

  return <>{children}</>;
}
