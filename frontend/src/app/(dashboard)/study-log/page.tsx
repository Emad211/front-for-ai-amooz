import { redirect } from 'next/navigation';

/**
 * The old «گزارش روزانه» standalone page. Its form now lives as the default
 * tab of the consolidated student advisor page («مشاور»), so this route is a
 * permanent redirect — old bookmarks and the study-log deep links keep
 * working.
 */
export default function StudyLogRedirectPage() {
  redirect('/advisory?tab=log');
}
