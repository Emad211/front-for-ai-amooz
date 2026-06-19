// components/layout/teacher-sidebar.tsx
'use client';

import { usePathname } from 'next/navigation';
import { SidebarContent } from './sidebar-content';
import { getTeacherNavMenu, ORG_NAV_MENU } from '@/constants/navigation';
import { useWorkspace } from '@/hooks/use-workspace';

export function TeacherSidebar() {
  const pathname = usePathname();
  // The org-MANAGER panel lives under /org and reuses this sidebar with the org nav.
  const isOrgPanel = pathname?.startsWith('/org') ?? false;
  const { isOrgMode, activeWorkspace } = useWorkspace();
  const navMenu = isOrgPanel ? ORG_NAV_MENU : getTeacherNavMenu(isOrgMode, activeWorkspace?.orgRole);
  const panelLabel = (isOrgPanel || isOrgMode) ? (activeWorkspace?.name ?? 'سازمان آموزشی') : 'پنل معلم';
  const logoHref = isOrgPanel ? '/org' : '/teacher';
  const settingsHref = isOrgPanel ? '/org/settings' : '/teacher/settings';

  return (
    <aside className="hidden lg:flex w-64 min-h-screen bg-card border-l border-border flex-col sticky top-0">
      <SidebarContent navMenu={navMenu} panelLabel={panelLabel} logoHref={logoHref} settingsHref={settingsHref} showWorkspaceSwitcher />
    </aside>
  );
}
