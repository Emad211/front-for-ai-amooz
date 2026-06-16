"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { OrganizationService } from '@/services/organization-service';
import { getStoredUser } from '@/services/auth-service';
import type { Workspace } from '@/types';

interface WorkspaceContextType {
  /** All orgs the user belongs to */
  workspaces: Workspace[];
  /** Currently active workspace (null = personal) */
  activeWorkspace: Workspace | null;
  /** Switch to an org workspace or back to personal (null) */
  switchWorkspace: (ws: Workspace | null) => void;
  /** Whether we're in org mode */
  isOrgMode: boolean;
  /** Whether the user may use a personal (freelancer) workspace at all */
  personalAllowed: boolean;
  /** Loading state */
  isLoading: boolean;
  /** Reload workspaces */
  reload: () => Promise<void>;
}

const WorkspaceContext = createContext<WorkspaceContextType>({
  workspaces: [],
  activeWorkspace: null,
  switchWorkspace: () => {},
  isOrgMode: false,
  personalAllowed: true,
  isLoading: true,
  reload: async () => {},
});

export const WORKSPACE_STORAGE_KEY = 'ai_amooz_active_workspace';

/**
 * Whether the current user may use a personal/freelancer workspace.
 * A MANAGER never can; a TEACHER can unless their account is org-only
 * (`is_freelancer === false`). Unknown/stale cached users default to allowed so
 * a rollout never strips an existing freelancer of their personal space.
 */
function computePersonalAllowed(): boolean {
  const u = getStoredUser();
  const role = (u?.role ?? '').toUpperCase();
  if (role === 'MANAGER') return false;
  return u?.is_freelancer !== false;
}

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [activeWorkspace, setActiveWorkspace] = useState<Workspace | null>(null);
  const [personalAllowed, setPersonalAllowed] = useState(true);
  const [isLoading, setIsLoading] = useState(true);

  const reload = useCallback(async () => {
    try {
      setIsLoading(true);
      const allowsPersonal = computePersonalAllowed();
      setPersonalAllowed(allowsPersonal);

      const data = await OrganizationService.getMyWorkspaces();
      setWorkspaces(data);

      // Restore the saved workspace if it still exists.
      const savedSlug = localStorage.getItem(WORKSPACE_STORAGE_KEY);
      let selected: Workspace | null = null;
      if (savedSlug) {
        selected = data.find((w) => w.slug === savedSlug) ?? null;
        if (!selected) localStorage.removeItem(WORKSPACE_STORAGE_KEY);
      }

      // No personal space (manager / org-only teacher) → default into an org
      // (prefer an admin/deputy one) so they are never stranded in an empty
      // personal view with no switcher to escape it.
      if (!selected && !allowsPersonal && data.length > 0) {
        selected =
          data.find((w) => w.orgRole === 'admin' || w.orgRole === 'deputy') ?? data[0];
      }

      setActiveWorkspace(selected);
    } catch {
      // User may not be logged in yet — silently fail
      setWorkspaces([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  // Recompute personal-space eligibility when the cached profile changes
  // (e.g. after login/profile update within the same tab).
  useEffect(() => {
    const onUserUpdate = () => setPersonalAllowed(computePersonalAllowed());
    window.addEventListener('user-profile-updated', onUserUpdate);
    return () => window.removeEventListener('user-profile-updated', onUserUpdate);
  }, []);

  const switchWorkspace = useCallback((ws: Workspace | null) => {
    setActiveWorkspace(ws);
    if (ws) {
      localStorage.setItem(WORKSPACE_STORAGE_KEY, ws.slug);
    } else {
      localStorage.removeItem(WORKSPACE_STORAGE_KEY);
    }
  }, []);

  return (
    <WorkspaceContext.Provider
      value={{
        workspaces,
        activeWorkspace,
        switchWorkspace,
        isOrgMode: activeWorkspace !== null,
        personalAllowed,
        isLoading,
        reload,
      }}
    >
      {children}
    </WorkspaceContext.Provider>
  );
}

export function useWorkspace() {
  return useContext(WorkspaceContext);
}
