'use client';

import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { GraduationCap, Users, BookOpen, Layers } from 'lucide-react';
import { useWorkspace } from '@/hooks/use-workspace';
import { OrganizationService } from '@/services/organization-service';
import { OrgModeGuard } from '@/components/organization/org-manager-guard';
import { formatPersianNumber } from '@/lib/persian-digits';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import type { StudyGroup } from '@/types';

export default function Page() {
  return (
    <OrgModeGuard>
      <PageInner />
    </OrgModeGuard>
  );
}

function PageInner() {
  const { activeWorkspace } = useWorkspace();
  const orgId = activeWorkspace?.id;

  const [groups, setGroups] = useState<StudyGroup[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (orgId) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orgId]);

  async function load() {
    if (!orgId) return;
    try {
      setLoading(true);
      const data = await OrganizationService.getMyStudyGroups(orgId);
      setGroups(data);
    } catch {
      toast.error('بارگیری گروه‌های آموزشی با خطا مواجه شد.');
    } finally {
      setLoading(false);
    }
  }

  if (!orgId) return null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="space-y-1">
        <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
          <GraduationCap className="h-6 w-6 text-primary" />
          گروه‌های من
        </h1>
        <p className="text-sm text-muted-foreground">
          گروه‌های آموزشی که در آن‌ها تدریس می‌کنید
        </p>
      </div>

      {/* Loading */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-28 rounded-2xl" />
          ))}
        </div>
      ) : groups.length === 0 ? (
        /* Empty state */
        <Card className="rounded-2xl border-border/50 shadow-sm">
          <CardContent className="flex flex-col items-center justify-center text-center gap-4 py-16">
            <div className="h-16 w-16 rounded-2xl bg-primary/10 flex items-center justify-center">
              <Users className="h-8 w-8 text-primary" />
            </div>
            <p className="text-sm text-muted-foreground max-w-md">
              هنوز به گروهی تخصیص داده نشده‌اید؛ با مدیر سازمان هماهنگ کنید.
            </p>
          </CardContent>
        </Card>
      ) : (
        /* Read-only grid of group cards */
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {groups.map((g) => (
            <Card
              key={g.id}
              className="rounded-2xl border-border/50 shadow-sm flex flex-col"
            >
              <CardHeader className="space-y-3">
                <div className="flex items-start justify-between gap-2">
                  <CardTitle className="text-base font-semibold leading-6">
                    {g.name}
                  </CardTitle>
                  <Badge
                    variant={g.status === 'active' ? 'default' : 'secondary'}
                    className="shrink-0"
                  >
                    {g.statusDisplay}
                  </Badge>
                </div>
                <div className="flex flex-wrap gap-2">
                  {g.gradeLabel ? (
                    <Badge variant="outline" className="font-normal">
                      {g.gradeLabel}
                    </Badge>
                  ) : null}
                  {g.subject ? (
                    <Badge variant="outline" className="font-normal">
                      {g.subject}
                    </Badge>
                  ) : null}
                </div>
              </CardHeader>
              <CardContent className="mt-auto">
                <div className="flex items-center gap-4 text-sm text-muted-foreground">
                  <span className="flex items-center gap-1.5">
                    <Users className="h-4 w-4" />
                    {formatPersianNumber(g.studentCount)} دانش‌آموز
                  </span>
                  <span className="flex items-center gap-1.5">
                    <BookOpen className="h-4 w-4" />
                    {formatPersianNumber(g.classCount)} کلاس
                  </span>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Footer summary */}
      {!loading && groups.length > 0 ? (
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Layers className="h-3.5 w-3.5" />
          مجموعاً {formatPersianNumber(groups.length)} گروه آموزشی
        </p>
      ) : null}
    </div>
  );
}
