// components/layout/teacher-sidebar.tsx
'use client';

import { SidebarContent } from './sidebar-content';
import { TEACHER_NAV_MENU, orgNavMenuForRole } from '@/constants/navigation';
import { useWorkspace } from '@/hooks/use-workspace';

export function TeacherSidebar() {
  const { isOrgMode, activeWorkspace } = useWorkspace();
  const navMenu = isOrgMode ? orgNavMenuForRole(activeWorkspace?.orgRole) : TEACHER_NAV_MENU;
  const panelLabel = isOrgMode ? (activeWorkspace?.name ?? 'سازمان') : 'پنل معلم';

  return (
    <aside className="hidden lg:flex w-64 min-h-screen bg-card border-l border-border flex-col sticky top-0">
      <SidebarContent navMenu={navMenu} panelLabel={panelLabel} logoHref="/teacher" settingsHref="/teacher/settings" />
    </aside>
  );
}
