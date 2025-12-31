// components/layout/teacher-sidebar.tsx
'use client';

import { SidebarContent } from './sidebar-content';
import { TEACHER_NAV_MENU } from '@/constants/navigation';

export function TeacherSidebar() {
  return (
    <aside className="hidden lg:flex w-64 min-h-screen bg-card border-l border-border flex-col sticky top-0">
      <SidebarContent navMenu={TEACHER_NAV_MENU} panelLabel="پنل معلم" logoHref="/teacher" settingsHref="/teacher/settings" />
    </aside>
  );
}
