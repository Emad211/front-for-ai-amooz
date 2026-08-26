'use client';

import { Clock } from 'lucide-react';

import { Card, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils';

/** Wire values accepted by the `?tab=` query param, in display order. */
export const STUDENT_DETAIL_TAB_KEYS = [
  'feed',
  'plan',
  'exams',
  'intake',
  'assess',
  'month',
  'challenges',
] as const;

export type StudentDetailTabKey = (typeof STUDENT_DETAIL_TAB_KEYS)[number];

type StudentDetailTab = {
  key: StudentDetailTabKey;
  /** Persian label shown in the tab bar. */
  label: string;
  /**
   * One-line Persian hint for the «به‌زودی» placeholder. Tabs that already
   * render a real card (feed/plan) leave this undefined — the presence of the
   * hint is what decides placeholder vs. real content on the page.
   */
  soonHint?: string;
};

/**
 * Single source of truth for tab order, labels, and placeholder copy.
 * When a later wave lands a real card for one of these tabs, remove its
 * `soonHint` and render the card in the page's content switch.
 */
export const STUDENT_DETAIL_TABS: readonly StudentDetailTab[] = [
  { key: 'feed', label: 'گزارش' },
  { key: 'plan', label: 'برنامه' },
  { key: 'exams', label: 'آزمون‌ها' },
  {
    key: 'intake',
    label: 'شناخت',
    soonHint: 'فرم شناخت دانش‌آموز و جدول کلاس‌های او به‌زودی اینجا فعال می‌شود.',
  },
  {
    key: 'assess',
    label: 'ارزیابی',
    soonHint: 'ارزیابی هفتگی و ثبت تماس‌ها به‌زودی اینجا فعال می‌شود.',
  },
  { key: 'month', label: 'ماه' },
  { key: 'challenges', label: 'چالش‌ها' },
];

/** Parse a raw `?tab=` value; missing or unknown falls back to `feed`. */
export function resolveStudentDetailTab(
  raw: string | null | undefined,
): StudentDetailTabKey {
  return (STUDENT_DETAIL_TAB_KEYS as readonly string[]).includes(raw ?? '')
    ? (raw as StudentDetailTabKey)
    : 'feed';
}

type StudentDetailTabsProps = {
  activeTab: StudentDetailTabKey;
  onTabChange: (key: StudentDetailTabKey) => void;
};

/**
 * The query-param-driven tab bar of the student detail page («گام ۱۱»).
 *
 * Controlled by the page: the page owns `?tab=` via useSearchParams and calls
 * router.replace on change, so deep links and back/forward stay consistent.
 * Mobile: horizontally scrollable RTL strip with ≥44px touch targets; desktop:
 * the pill row centers inside the page's max-w-4xl column (w-max + mx-auto
 * keeps centering without clipping when the row overflows).
 */
export function StudentDetailTabs({ activeTab, onTabChange }: StudentDetailTabsProps) {
  return (
    <div
      role="tablist"
      aria-label="بخش‌های پروندۀ دانش‌آموز"
      className="overflow-x-auto whitespace-nowrap"
    >
      <div className="mx-auto flex w-max items-center gap-1">
        {STUDENT_DETAIL_TABS.map((tab) => {
          const selected = tab.key === activeTab;
          return (
            <button
              key={tab.key}
              type="button"
              role="tab"
              aria-selected={selected}
              onClick={() => onTabChange(tab.key)}
              className={cn(
                'flex h-11 shrink-0 items-center rounded-full px-4 text-sm font-medium transition-colors',
                selected
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground',
              )}
            >
              {tab.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/**
 * Placeholder card for tabs whose real cards land in later waves — never a
 * removed tab, so the IA stays stable from day one. Mirrors the page's
 * NotFoundState visual language (dashed border, centered, muted copy).
 */
export function StudentDetailTabPlaceholder({ tabKey }: { tabKey: StudentDetailTabKey }) {
  const tab = STUDENT_DETAIL_TABS.find((t) => t.key === tabKey);
  if (!tab?.soonHint) return null;

  return (
    <Card className="border-dashed">
      <CardContent className="py-12 text-center">
        <Clock className="mx-auto h-8 w-8 text-muted-foreground/60" />
        <p className="mt-3 text-sm font-medium">به‌زودی</p>
        <p className="mx-auto mt-1 max-w-md text-xs leading-relaxed text-muted-foreground">
          {tab.soonHint}
        </p>
      </CardContent>
    </Card>
  );
}
