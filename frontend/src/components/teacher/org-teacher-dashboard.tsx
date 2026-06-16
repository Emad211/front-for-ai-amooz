'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useWorkspace } from '@/hooks/use-workspace';
import { OrganizationService } from '@/services/organization-service';
import type { StudyGroup } from '@/types';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Users, GraduationCap, Building2 } from 'lucide-react';
import { formatPersianNumber } from '@/lib/persian-digits';

/**
 * Group-centric dashboard for an organization TEACHER: the study groups
 * (گروه آموزشی) a manager has assigned them to, with each group's roster.
 */
export function OrgTeacherDashboard() {
  const { activeWorkspace } = useWorkspace();
  const [groups, setGroups] = useState<StudyGroup[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!activeWorkspace) return;
    let cancelled = false;
    setGroups(null);
    setError(null);
    OrganizationService.getMyStudyGroups(activeWorkspace.id)
      .then((data) => { if (!cancelled) setGroups(data); })
      .catch(() => { if (!cancelled) setError('خطا در دریافت گروه‌های آموزشی'); });
    return () => { cancelled = true; };
  }, [activeWorkspace]);

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          {activeWorkspace?.logo ? (
            <img src={activeWorkspace.logo} alt={activeWorkspace.name} className="h-10 w-10 rounded-xl object-cover" />
          ) : (
            <div className="h-10 w-10 rounded-xl bg-primary/10 flex items-center justify-center">
              <Building2 className="h-5 w-5 text-primary" />
            </div>
          )}
          <div>
            <h1 className="text-2xl font-black text-foreground">گروه‌های آموزشی من</h1>
            <p className="text-sm text-muted-foreground">{activeWorkspace?.name}</p>
          </div>
        </div>
        <Button variant="outline" size="sm" asChild>
          <Link href="/teacher/my-classes">کلاس‌های من</Link>
        </Button>
      </div>

      {/* Loading */}
      {groups === null && !error && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-40 rounded-2xl" />)}
        </div>
      )}

      {error && <p className="text-destructive text-center py-12">{error}</p>}

      {/* Empty */}
      {groups && groups.length === 0 && (
        <Card className="rounded-2xl border-dashed">
          <CardContent className="py-16 text-center">
            <GraduationCap className="w-10 h-10 text-muted-foreground mx-auto mb-3" />
            <p className="font-medium">هنوز به گروهی اضافه نشده‌اید</p>
            <p className="text-xs text-muted-foreground mt-1">مدیر سازمان شما را به گروه‌های آموزشی اضافه می‌کند.</p>
          </CardContent>
        </Card>
      )}

      {/* Groups grid */}
      {groups && groups.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {groups.map((g) => (
            <Card key={g.id} className="rounded-2xl border-border/50 shadow-sm">
              <CardHeader className="pb-2">
                <CardTitle className="text-lg font-bold flex items-center gap-2">
                  <span className="flex-1 truncate">{g.name}</span>
                  <Badge variant="secondary" className="text-[10px] shrink-0">
                    {formatPersianNumber(g.studentCount)} دانش‌آموز
                  </Badge>
                </CardTitle>
                {(g.gradeLabel || g.subject || g.classCount > 0) && (
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {g.gradeLabel && <Badge variant="outline" className="text-[10px]">{g.gradeLabel}</Badge>}
                    {g.subject && <Badge variant="outline" className="text-[10px]">{g.subject}</Badge>}
                    {g.classCount > 0 && <Badge variant="outline" className="text-[10px]">{formatPersianNumber(g.classCount)} کلاس</Badge>}
                  </div>
                )}
              </CardHeader>
              <CardContent>
                {g.students && g.students.length > 0 ? (
                  <ul className="space-y-1">
                    {g.students.slice(0, 6).map((s) => (
                      <li key={s.id} className="flex items-center gap-2 text-sm">
                        <Users className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                        <span className="truncate">{s.name}</span>
                      </li>
                    ))}
                    {g.students.length > 6 && (
                      <li className="text-xs text-muted-foreground ps-5">
                        + {formatPersianNumber(g.students.length - 6)} نفر دیگر
                      </li>
                    )}
                  </ul>
                ) : (
                  <p className="text-xs text-muted-foreground">دانش‌آموزی در این گروه نیست.</p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
