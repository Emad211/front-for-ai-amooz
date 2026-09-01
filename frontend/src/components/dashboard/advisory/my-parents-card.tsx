'use client';

import { useEffect, useState } from 'react';
import { Users } from 'lucide-react';

import {
  AdvisoryService,
  type MyParentsResponse,
} from '@/services/advisory-service';
import { PARENT_RELATION_LABELS } from '@/components/advisory/parent-links-card';
import { toPersianDigits } from '@/lib/persian-digits';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';

/**
 * The student-side transparency mirror — «والدین متصل»: which parents the
 * advisor has linked to this student's weekly report.
 *
 * Follows the same *quiet* rule as MySubjectsCard: it renders nothing at all —
 * no skeleton, no empty card — until it knows there are parents to show. A
 * student whose advisor has linked no parents sees nothing new here, and a
 * failed fetch (including a not-yet-active engagement) is swallowed for the
 * same reason.
 */
export function MyParentsCard() {
  const [data, setData] = useState<MyParentsResponse | null>(null);

  useEffect(() => {
    let active = true;
    AdvisoryService.getMyParents()
      .then((res) => {
        if (active) setData(res);
      })
      .catch(() => {
        // Silent by design — see the component docstring.
      });
    return () => {
      active = false;
    };
  }, []);

  if (!data || data.parents.length === 0) return null;

  return (
    <Card dir="rtl" className="rounded-2xl border-primary/20 bg-primary/5">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base font-semibold">
          <span className="rounded-lg bg-primary/10 p-1.5">
            <Users className="h-4 w-4 text-primary" />
          </span>
          والدین متصل
        </CardTitle>
        <CardDescription className="text-xs leading-relaxed text-muted-foreground">
          این افراد گزارش هفتگی‌ات را می‌بینند.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ul className="divide-y divide-border/60">
          {data.parents.map((parent) => (
            <li
              key={parent.id}
              className="flex items-center justify-between gap-3 py-2.5"
            >
              <span className="text-sm font-medium">
                {PARENT_RELATION_LABELS[parent.relation] ?? parent.relation}
              </span>
              <span
                dir="ltr"
                className="text-xs tabular-nums text-muted-foreground"
              >
                {toPersianDigits(parent.phoneMasked)}
              </span>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
