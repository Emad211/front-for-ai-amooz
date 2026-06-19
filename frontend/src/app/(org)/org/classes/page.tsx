'use client';

import { useEffect, useState } from 'react';
import { useWorkspace } from '@/hooks/use-workspace';
import { OrganizationService } from '@/services/organization-service';
import type { OrgClassRow } from '@/types';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Input } from '@/components/ui/input';
import { BookOpen, Search } from 'lucide-react';
import { formatPersianNumber } from '@/lib/persian-digits';
import { formatPersianDate } from '@/lib/date-utils';

/** Manager oversight: every class/exam in the org (all teachers), read-only. */
export default function OrgClassesPage() {
  const { activeWorkspace, isOrgMode, isLoading } = useWorkspace();
  const [rows, setRows] = useState<OrgClassRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');

  const isOrgManager =
    isOrgMode && (activeWorkspace?.orgRole === 'admin' || activeWorkspace?.orgRole === 'deputy');

  useEffect(() => {
    if (!isOrgManager || !activeWorkspace) return;
    let cancelled = false;
    setRows(null);
    setError(null);
    OrganizationService.getOrgClasses(activeWorkspace.id)
      .then((d) => { if (!cancelled) setRows(d); })
      .catch(() => { if (!cancelled) setError('خطا در دریافت کلاس‌های سازمان آموزشی'); });
    return () => { cancelled = true; };
  }, [isOrgManager, activeWorkspace]);

  if (isLoading) return <Skeleton className="h-96 rounded-2xl" />;
  if (!isOrgManager || !activeWorkspace) {
    return (
      <p className="text-muted-foreground text-center py-12">
        برای دیدن کلاس‌ها، سازمان آموزشیِ تحت مدیریت خود را از سوییچر انتخاب کنید.
      </p>
    );
  }

  const q = search.trim().toLowerCase();
  const filtered = (rows ?? []).filter(
    (r) => !q || r.title.toLowerCase().includes(q) || r.teacherName.toLowerCase().includes(q),
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-black text-foreground">کلاس‌های سازمان آموزشی</h1>
        <p className="text-sm text-muted-foreground mt-1">
          نظارت بر همهٔ کلاس‌ها و آزمون‌های ساخته‌شده در «{activeWorkspace.name}»
        </p>
      </div>

      <div className="relative max-w-sm">
        <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <Input
          placeholder="جستجوی عنوان یا معلم…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pr-9 rounded-xl"
        />
      </div>

      {rows === null && !error ? (
        <div className="space-y-3">{[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-16 rounded-xl" />)}</div>
      ) : error ? (
        <p className="text-destructive text-center py-12">{error}</p>
      ) : filtered.length === 0 ? (
        <Card className="rounded-2xl border-dashed">
          <CardContent className="py-16 text-center">
            <BookOpen className="w-10 h-10 text-muted-foreground mx-auto mb-3" />
            <p className="font-medium">کلاسی یافت نشد</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2">
          {filtered.map((c) => (
            <Card key={c.id} className="rounded-xl hover:shadow-sm transition-shadow">
              <CardContent className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="text-sm font-bold truncate">{c.title || 'بدون عنوان'}</p>
                    <Badge variant="outline" className="text-[10px]">
                      {c.pipelineType === 'exam_prep' ? 'آمادگی آزمون' : 'کلاس'}
                    </Badge>
                    {c.studyGroupName && <Badge variant="outline" className="text-[10px]">{c.studyGroupName}</Badge>}
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    معلم: {c.teacherName || '—'} · {formatPersianNumber(c.studentCount)} دانش‌آموز · {formatPersianDate(c.createdAt)}
                  </p>
                </div>
                <Badge
                  variant={c.isPublished ? 'default' : 'outline'}
                  className="text-[10px] shrink-0 self-end sm:self-auto"
                >
                  {c.isPublished ? 'منتشر شده' : 'در حال آماده‌سازی'}
                </Badge>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
