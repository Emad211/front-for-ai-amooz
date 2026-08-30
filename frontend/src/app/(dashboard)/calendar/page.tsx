import { redirect } from 'next/navigation';

/**
 * The student calendar now lives as the «تقویم» tab of the consolidated
 * advisor page, fed by the merged loader (exercise deadlines, exam-prep,
 * study-plan rows, monthly-outlook entries, challenge days). This route is a
 * permanent redirect so old links keep working.
 */
export default function CalendarRedirectPage() {
  redirect('/advisory?tab=calendar');
}
