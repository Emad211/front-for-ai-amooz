"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { OrganizationService } from '@/services/organization-service';
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
  /**
   * Whether the user is an org **manager** (org_role admin/deputy in some org).
   * Managers are management-only: they are locked into their org workspace and
   * never get a personal/freelance mode, so the workspace switcher is hidden.
   */
  isManager: boolean;
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
  isManager: false,
  isLoading: true,
  reload: async () => {},
});

const STORAGE_KEY = 'ai_amooz_active_workspace';

/** A workspace where the user is a manager (admin/deputy). */
function isManagerWorkspace(ws: Workspace): boolean {
  return ws.orgRole === 'admin' || ws.orgRole === 'deputy';
}

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [activeWorkspace, setActiveWorkspace] = useState<Workspace | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const reload = useCallback(async () => {
    try {
      setIsLoading(true);
      const data = await OrganizationService.getMyWorkspaces();
      setWorkspaces(data);

      const managerWs = data.find(isManagerWorkspace) ?? null;
      const savedSlug = localStorage.getItem(STORAGE_KEY);
      let next: Workspace | null = savedSlug
        ? (data.find((w) => w.slug === savedSlug) ?? null)
        : null;

      // Managers are locked into org mode — they never get a personal/freelance
      // workspace. If nothing valid is saved, default to their org.
      if (managerWs && !next) {
        next = managerWs;
      }

      setActiveWorkspace(next);
      if (next) {
        localStorage.setItem(STORAGE_KEY, next.slug);
      } else if (savedSlug) {
        // Clear a stale slug whose workspace no longer exists.
        localStorage.removeItem(STORAGE_KEY);
      }
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

  const isManager = workspaces.some(isManagerWorkspace);

  const switchWorkspace = useCallback((ws: Workspace | null) => {
    // A manager cannot drop into personal/freelance mode.
    if (ws === null && workspaces.some(isManagerWorkspace)) return;
    setActiveWorkspace(ws);
    if (ws) {
      localStorage.setItem(STORAGE_KEY, ws.slug);
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, [workspaces]);

  return (
    <WorkspaceContext.Provider
      value={{
        workspaces,
        activeWorkspace,
        switchWorkspace,
        isOrgMode: activeWorkspace !== null,
        isManager,
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
