import type { CalendarEvent, EventPriority } from '@/types';
import { DashboardService } from '@/services/dashboard-service';
import {
  AdvisoryService,
  type MyChallengesResponse,
  type MyMonthlyOutlookResponse,
  type MyPlansResponse,
} from '@/services/advisory-service';
import { gregorianIsoToJalaliKey, jalaliMonthStartIso } from '@/lib/calendar';
import { toPersianDigits } from '@/lib/persian-digits';

export type AdvisorCalendarSources = {
  baseEvents: () => Promise<CalendarEvent[]>;
  plans: () => Promise<MyPlansResponse>;
  monthlyOutlook: (monthStartIso: string) => Promise<MyMonthlyOutlookResponse>;
  challenges: () => Promise<MyChallengesResponse>;
};

export const advisorCalendarSources: AdvisorCalendarSources = {
  baseEvents: () => DashboardService.getCalendarEvents(),
  plans: () => AdvisoryService.getMyPlans(),
  monthlyOutlook: (monthStartIso: string) =>
    AdvisoryService.getMyMonthlyOutlook(monthStartIso),
  challenges: () => AdvisoryService.getMyChallenges(),
};

const MASTERY_PRIORITY: Record<string, EventPriority> = {
  RED: 'high',
  YELLOW: 'medium',
  GREEN: 'low',
};

function planItemEvents(sources: MyPlansResponse): CalendarEvent[] {
  const events: CalendarEvent[] = [];
  for (const plan of sources.plans) {
    if (plan.status !== 'PUBLISHED') continue;
    for (const item of plan.items) {
      const date = gregorianIsoToJalaliKey(item.date);
      if (!date) continue;
      const details = [item.topic?.trim(), item.unitLabel?.trim()]
        .filter(Boolean)
        .join(' · ');
      events.push({
        id: `plan-${plan.id}-d${item.dayOffset}-s${item.subjectId}`,
        title: `${item.name} · ${toPersianDigits(item.plannedMinutes)} دقیقه`,
        description: details || 'برنامهٔ مطالعهٔ مشاور برای این روز',
        date,
        type: 'study_plan',
        priority: (item.masteryColor && MASTERY_PRIORITY[item.masteryColor]) || 'low',
        subject: item.name,
      });
    }
  }
  return events;
}

function outlookEntryEvents(
  sources: MyMonthlyOutlookResponse,
  monthStartIso: string,
): CalendarEvent[] {
  if (!sources.active || !sources.outlook) return [];
  return sources.outlook.entries.flatMap((entry, index) => {
    const date = gregorianIsoToJalaliKey(entry.date);
    if (!date) return [];
    const description = [entry.academicNote.trim(), entry.tasks.trim()]
      .filter(Boolean)
      .join('\n');
    return [
      {
        id: `outlook-${monthStartIso}-${index}`,
        title: entry.event.trim() || 'برنامهٔ مشاور',
        description: description || 'یادداشت ماهانهٔ مشاور برای این روز',
        date,
        type: 'advisor_note' as const,
        priority: 'low' as const,
      },
    ];
  });
}

function challengeDayIso(startDate: string, dayNumber: number): string | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(startDate);
  if (!match) return null;
  const date = new Date(
    Number(match[1]),
    Number(match[2]) - 1,
    Number(match[3]) + dayNumber - 1,
  );
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function challengeDayEvents(sources: MyChallengesResponse): CalendarEvent[] {
  if (!sources.active) return [];
  const events: CalendarEvent[] = [];
  for (const challenge of sources.challenges) {
    for (const day of challenge.days) {
      const iso = challengeDayIso(challenge.startDate, day.dayNumber);
      const date = iso ? gregorianIsoToJalaliKey(iso) : null;
      if (!date) continue;
      events.push({
        id: `challenge-${challenge.id}-d${day.dayNumber}`,
        title: `چالش: ${challenge.title || 'بدون عنوان'} · روز ${toPersianDigits(day.dayNumber)}`,
        description: day.goal.trim() || 'روزِ چالش هفت‌روزه',
        date,
        type: 'challenge',
        priority: challenge.status === 'ACTIVE' ? 'medium' : 'low',
      });
    }
  }
  return events;
}

/**
 * The merged student calendar: exercise deadlines + scheduled exam-prep (base)
 * plus the advisor artifacts that carry dates — published study-plan rows,
 * the viewed month's outlook entries and 7-day challenge days. Advisory reads
 * are quiet by contract (no advisor ⇒ empty), and any advisory failure only
 * drops its own layer so the base calendar still renders.
 */
export async function getAdvisorCalendarEvents(
  jYear: number,
  jMonth: number,
  sources: AdvisorCalendarSources = advisorCalendarSources,
): Promise<CalendarEvent[]> {
  const monthStartIso = jalaliMonthStartIso(jYear, jMonth);

  const [base, plans, outlook, challenges] = await Promise.all([
    sources.baseEvents().catch(() => [] as CalendarEvent[]),
    sources.plans().catch(() => null),
    sources.monthlyOutlook(monthStartIso).catch(() => null),
    sources.challenges().catch(() => null),
  ]);

  const merged = [
    ...base,
    ...(plans ? planItemEvents(plans) : []),
    ...(outlook ? outlookEntryEvents(outlook, monthStartIso) : []),
    ...(challenges ? challengeDayEvents(challenges) : []),
  ];
  return merged.sort((a, b) =>
    `${a.date} ${a.time ?? ''}`.localeCompare(`${b.date} ${b.time ?? ''}`),
  );
}
