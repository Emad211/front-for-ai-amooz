'use client';

import { useEffect, useState } from 'react';
import { useWorkspace } from '@/hooks/use-workspace';
import { OrganizationService } from '@/services/organization-service';
import type { OrgCosts } from '@/types';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Coins, Users, BookOpen, GraduationCap, Layers, type LucideIcon } from 'lucide-react';
import { formatPersianNumber } from '@/lib/persian-digits';

const FEATURE_LABELS: Record<string, string> = {
  transcription: 'رونویسی',
  structure: 'ساختاردهی',
  prereq_extract: 'استخراج پیش‌نیاز',
  prereq_teach: 'آموزش پیش‌نیاز',
  recap: 'خلاصه',
  exam_prep_structure: 'ساختار آمادگی آزمون',
  pdf_extraction: 'استخراج PDF',
  quiz_generation: 'تولید کوییز',
  quiz_grading: 'تصحیح کوییز',
  final_exam_generation: 'تولید آزمون پایانی',
  hint_generation: 'راهنمایی',
  chat_course: 'گفتگوی درس',
  chat_exam_prep: 'گفتگوی آزمون',
  chat_vision: 'بینایی گفتگو',
};

const toman = (n: number) => `${formatPersianNumber(Math.round(n))} تومان`;

function BreakdownCard({
  title,
  icon: Icon,
  rows,
}: {
  title: string;
  icon: LucideIcon;
  rows: { label: string; toman: number }[];
}) {
  const max = Math.max(1, ...rows.map((r) => r.toman));
  return (
    <Card className="rounded-2xl">
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-bold flex items-center gap-2">
          <Icon className="w-4 h-4" />
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2.5">
        {rows.length === 0 ? (
          <p className="text-xs text-muted-foreground">داده‌ای نیست.</p>
        ) : (
          rows.map((r, i) => (
            <div key={i} className="space-y-1">
              <div className="flex items-center justify-between gap-2 text-sm">
                <span className="truncate">{r.label}</span>
                <span className="tabular-nums shrink-0 text-muted-foreground">{toman(r.toman)}</span>
              </div>
              <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                <div className="h-full bg-primary rounded-full" style={{ width: `${Math.min(100, (r.toman / max) * 100)}%` }} />
              </div>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}

/** Manager cost dashboard: total org AI cost + breakdown by teacher/group/class/feature. */
export default function OrgCostsPage() {
  const { activeWorkspace, isOrgMode, isLoading } = useWorkspace();
  const [costs, setCosts] = useState<OrgCosts | null>(null);
  const [error, setError] = useState<string | null>(null);

  const isOrgManager =
    isOrgMode && (activeWorkspace?.orgRole === 'admin' || activeWorkspace?.orgRole === 'deputy');

  useEffect(() => {
    if (!isOrgManager || !activeWorkspace) return;
    let cancelled = false;
    setCosts(null);
    setError(null);
    OrganizationService.getOrgCosts(activeWorkspace.id)
      .then((d) => { if (!cancelled) setCosts(d); })
      .catch(() => { if (!cancelled) setError('خطا در دریافت هزینه‌ها'); });
    return () => { cancelled = true; };
  }, [isOrgManager, activeWorkspace]);

  if (isLoading) return <Skeleton className="h-96 rounded-2xl" />;
  if (!isOrgManager || !activeWorkspace) {
    return (
      <p className="text-muted-foreground text-center py-12">
        برای دیدن هزینه‌ها، سازمان آموزشیِ تحت مدیریت خود را از سوییچر انتخاب کنید.
      </p>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-black text-foreground">هزینه‌های هوش مصنوعی</h1>
        <p className="text-sm text-muted-foreground mt-1">
          هزینهٔ پردازش‌های هوش مصنوعیِ «{activeWorkspace.name}» به تفکیک معلم، گروه، کلاس و نوع پردازش
        </p>
      </div>

      {costs === null && !error ? (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => <Skeleton key={i} className="h-28 rounded-2xl" />)}
        </div>
      ) : error ? (
        <p className="text-destructive text-center py-12">{error}</p>
      ) : costs ? (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <Card className="rounded-2xl">
              <CardContent className="flex items-center gap-4 p-5">
                <div className="h-12 w-12 rounded-xl bg-amber-500/10 flex items-center justify-center"><Coins className="h-6 w-6 text-amber-500" /></div>
                <div><p className="text-sm text-muted-foreground">هزینهٔ کل</p><p className="text-2xl font-bold">{toman(costs.total.toman)}</p></div>
              </CardContent>
            </Card>
            <Card className="rounded-2xl">
              <CardContent className="flex items-center gap-4 p-5">
                <div className="h-12 w-12 rounded-xl bg-blue-500/10 flex items-center justify-center"><Layers className="h-6 w-6 text-blue-500" /></div>
                <div><p className="text-sm text-muted-foreground">توکن مصرفی</p><p className="text-2xl font-bold">{formatPersianNumber(costs.total.tokens)}</p></div>
              </CardContent>
            </Card>
            <Card className="rounded-2xl">
              <CardContent className="flex items-center gap-4 p-5">
                <div className="h-12 w-12 rounded-xl bg-purple-500/10 flex items-center justify-center"><BookOpen className="h-6 w-6 text-purple-500" /></div>
                <div><p className="text-sm text-muted-foreground">تعداد فراخوانی</p><p className="text-2xl font-bold">{formatPersianNumber(costs.total.calls)}</p></div>
              </CardContent>
            </Card>
          </div>

          <BreakdownCard title="به تفکیک معلم" icon={Users} rows={costs.byTeacher.map((r) => ({ label: r.teacherName, toman: r.toman }))} />
          <BreakdownCard title="به تفکیک گروه آموزشی" icon={GraduationCap} rows={costs.byGroup.map((r) => ({ label: r.studyGroupName, toman: r.toman }))} />
          <BreakdownCard title="به تفکیک کلاس" icon={BookOpen} rows={costs.byClass.map((r) => ({ label: `${r.title || 'بدون عنوان'} — ${r.teacherName}`, toman: r.toman }))} />
          <BreakdownCard title="به تفکیک نوع پردازش" icon={Coins} rows={costs.byFeature.map((r) => ({ label: FEATURE_LABELS[r.feature] ?? r.feature, toman: r.toman }))} />
        </>
      ) : null}
    </div>
  );
}
