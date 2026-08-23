'use client';

import { useEffect, useMemo, useState } from 'react';
import { CalendarCheck2 } from 'lucide-react';

import {
  AdvisoryService,
  type StudyPlanItemOut,
  type StudyPlanOut,
} from '@/services/advisory-service';
import { toPersianDigits } from '@/lib/persian-digits';
import { adherenceColorClass, formatAdherence } from '@/lib/adherence';
import { formatPersianDate } from '@/lib/date-utils';
import { Badge } from '@/components/ui/badge';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';

/** Local "today" as ISO `YYYY-MM-DD`, so range checks stay pure string compares
 * and no timezone can shift a day boundary. */
function todayIso(): string {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return `${now.getFullYear()}-${month}-${day}`;
}

/** The plan running today, else the nearest future one; null when neither. */
function pickCurrentOrNext(plans: StudyPlanOut[]): StudyPlanOut | null {
  const today = todayIso();
  const current = plans.find((p) => p.startDate <= today && today <= p.endDate);
  if (current) return current;
  const upcoming = plans
    .filter((p) => p.startDate > today)
    .sort((a, b) => a.startDate.localeCompare(b.startDate));
  return upcoming[0] ?? null;
}

/**
 * The student's «برنامه مطالعه» card on dashboard home.
 *
 * Shows exactly one plan — the one running today, else the nearest upcoming —
 * with its rows grouped by day. Follows the quiet rule of MySubjectsCard: it
 * renders nothing at all (no skeleton, no empty card) until there is a plan to
 * show, because most students have no advisor and must not pay layout cost for
 * it. A failed fetch is swallowed for the same reason.
 */
export function StudyPlanCard() {
  const [plans, setPlans] = useState<StudyPlanOut[] | null>(null);

  useEffect(() => {
    let active = true;
    AdvisoryService.getMyPlans()
      .then((res) => {
        // Server sends PUBLISHED only, but filter defensively anyway: a DRAFT
        // leaking into this list would be visible to the student.
        if (active) setPlans(res.plans.filter((p) => p.status === 'PUBLISHED'));
      })
      .catch(() => {
        // Silent by design — see the component docstring.
      });
    return () => {
      active = false;
    };
  }, []);

  const plan = useMemo(() => (plans ? pickCurrentOrNext(plans) : null), [plans]);

  const groupedItems = useMemo(() => {
    if (!plan) return [];
    const byDay = new Map<number, StudyPlanItemOut[]>();
    for (const item of plan.items) {
      const bucket = byDay.get(item.dayOffset);
      if (bucket) bucket.push(item);
      else byDay.set(item.dayOffset, [item]);
    }
    return [...byDay.entries()].sort((a, b) => a[0] - b[0]);
  }, [plan]);

  if (!plan) return null;

  const isCurrent = plan.startDate <= todayIso() && todayIso() <= plan.endDate;

  return (
    <Card dir="rtl" className="rounded-2xl border-primary/20 bg-primary/5">
      <CardHeader className="pb-3">
        <CardTitle className="flex flex-wrap items-center gap-2 text-base font-semibold">
          <span className="rounded-lg bg-primary/10 p-1.5">
            <CalendarCheck2 className="h-4 w-4 text-primary" />
          </span>
          برنامه مطالعه
          <Badge variant={isCurrent ? 'default' : 'secondary'} className="font-normal">
            {isCurrent ? 'جاری' : 'به‌زودی'}
          </Badge>
        </CardTitle>
        <p className="text-xs leading-relaxed text-muted-foreground">
          از {formatPersianDate(plan.startDate)} تا {formatPersianDate(plan.endDate)} ·{' '}
          {toPersianDigits(plan.durationDays)} روز
        </p>
        {/* Step 8: adherence percent + slim bar; only for the running plan —
        upcoming plans arrive with percent null (nothing elapsed yet). */}
        {isCurrent && plan.percent != null && (
          <div className="mt-2 space-y-1.5">
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs text-muted-foreground">پایبندی به برنامه</span>
              <span
                className={`rounded-full px-2 py-0.5 text-xs font-semibold tabular-nums ${adherenceColorClass(plan.percent)}`}
              >
                {formatAdherence(plan.percent)}
              </span>
            </div>
            <div
              role="progressbar"
              aria-valuenow={plan.percent}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label="پایبندی به برنامه"
              className="h-1.5 w-full overflow-hidden rounded-full bg-muted"
            >
              <div
                className={`h-full rounded-full ${
                  plan.percent >= 80
                    ? 'bg-emerald-500'
                    : plan.percent >= 50
                      ? 'bg-amber-500'
                      : 'bg-red-500'
                }`}
                style={{ width: `${Math.min(100, Math.max(0, plan.percent))}%` }}
              />
            </div>
          </div>
        )}
      </CardHeader>
      <CardContent>
        {groupedItems.length === 0 ? (
          <p className="text-xs leading-relaxed text-muted-foreground">
            هنوز ردیفی در این برنامه ثبت نشده است.
          </p>
        ) : (
          <ScrollArea className="max-h-64 pe-2">
            <ul className="space-y-2.5">
              {groupedItems.map(([dayOffset, items]) => (
                <li key={dayOffset}>
                  <p className="text-xs font-medium">
                    روز {toPersianDigits(dayOffset + 1)}
                    <span className="ms-1.5 font-normal text-muted-foreground">
                      {formatPersianDate(items[0]?.date ?? plan.startDate)}
                    </span>
                  </p>
                  <ul className="mt-1 space-y-0.5 border-s border-border/60 ps-3">
                    {items.map((item) => (
                      <li
                        key={`${item.subjectId}`}
                        className="flex items-center justify-between gap-2 text-xs"
                      >
                        <span className="min-w-0 truncate">{item.name}</span>
                        <span className="shrink-0 tabular-nums text-muted-foreground">
                          {toPersianDigits(item.plannedMinutes)} دقیقه
                        </span>
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
          </ScrollArea>
        )}
      </CardContent>
    </Card>
  );
}
