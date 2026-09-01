'use client';

import { useRef } from 'react';
import type { KeyboardEvent } from 'react';
import { BarChart3, CalendarRange, ClipboardCheck, FolderOpen } from 'lucide-react';

import { cn } from '@/lib/utils';

export const STUDENT_DETAIL_TAB_KEYS = ['decision', 'activity', 'plan', 'record'] as const;

export type StudentDetailTabKey = (typeof STUDENT_DETAIL_TAB_KEYS)[number];

const LEGACY_TAB_ALIASES: Record<string, StudentDetailTabKey> = {
  feed: 'activity',
  exams: 'record',
  intake: 'record',
  assess: 'record',
  month: 'record',
  challenges: 'record',
};

const STUDENT_DETAIL_TABS = [
  { key: 'decision', label: 'تصمیم امروز', icon: ClipboardCheck },
  { key: 'activity', label: 'گزارش مطالعه', icon: BarChart3 },
  { key: 'plan', label: 'برنامه‌ریزی', icon: CalendarRange },
  { key: 'record', label: 'پرونده', icon: FolderOpen },
] as const;

export function resolveStudentDetailTab(raw: string | null | undefined): StudentDetailTabKey {
  if (raw && (STUDENT_DETAIL_TAB_KEYS as readonly string[]).includes(raw)) {
    return raw as StudentDetailTabKey;
  }
  return raw ? LEGACY_TAB_ALIASES[raw] ?? 'decision' : 'decision';
}

export function studentDetailTabId(key: StudentDetailTabKey): string {
  return `student-detail-tab-${key}`;
}

export function studentDetailPanelId(key: StudentDetailTabKey): string {
  return `student-detail-panel-${key}`;
}

type StudentDetailTabsProps = {
  activeTab: StudentDetailTabKey;
  onTabChange: (key: StudentDetailTabKey) => void;
};

export function StudentDetailTabs({ activeTab, onTabChange }: StudentDetailTabsProps) {
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);

  const handleKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    let nextIndex: number | null = null;
    if (event.key === 'ArrowLeft') nextIndex = (index + 1) % STUDENT_DETAIL_TABS.length;
    if (event.key === 'ArrowRight') {
      nextIndex = (index - 1 + STUDENT_DETAIL_TABS.length) % STUDENT_DETAIL_TABS.length;
    }
    if (event.key === 'Home') nextIndex = 0;
    if (event.key === 'End') nextIndex = STUDENT_DETAIL_TABS.length - 1;
    if (nextIndex === null) return;
    event.preventDefault();
    const nextTab = STUDENT_DETAIL_TABS[nextIndex];
    if (!nextTab) return;
    onTabChange(nextTab.key);
    tabRefs.current[nextIndex]?.focus();
  };

  return (
    <div className="overflow-x-auto rounded-2xl border border-border/60 bg-card p-1.5">
      <div role="tablist" aria-label="کارهای پروندهٔ دانش‌آموز" className="flex min-w-max gap-1">
        {STUDENT_DETAIL_TABS.map((tab, index) => {
          const selected = tab.key === activeTab;
          return (
            <button
              key={tab.key}
              ref={(node) => {
                tabRefs.current[index] = node;
              }}
              id={studentDetailTabId(tab.key)}
              type="button"
              role="tab"
              tabIndex={selected ? 0 : -1}
              aria-selected={selected}
              aria-controls={studentDetailPanelId(tab.key)}
              onClick={() => onTabChange(tab.key)}
              onKeyDown={(event) => handleKeyDown(event, index)}
              className={cn(
                'flex h-11 shrink-0 items-center gap-2 rounded-xl px-4 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
                selected
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground',
              )}
            >
              <tab.icon className="h-4 w-4" />
              {tab.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
