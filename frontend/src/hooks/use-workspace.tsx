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
  isLoading: true,
  reload: async () => {},
});

const STORAGE_KEY = 'ai_amooz_active_workspace';

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [activeWorkspace, setActiveWorkspace] = useState<Workspace | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const reload = useCallback(async () => {
    try {
      setIsLoading(true);
      const data = await OrganizationService.getMyWorkspaces();
      setWorkspaces(data);

      // Restore saved workspace
      const savedSlug = localStorage.getItem(STORAGE_KEY);
      if (savedSlug) {
        const saved = data.find((w) => w.slug === savedSlug) ?? null;
        setActiveWorkspace(saved);
        // Clear stale slug if the saved workspace no longer exists
        if (!saved) {
          localStorage.removeItem(STORAGE_KEY);
        }
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

  const switchWorkspace = useCallback((ws: Workspace | null) => {
    setActiveWorkspace(ws);
    if (ws) {
      localStorage.setItem(STORAGE_KEY, ws.slug);
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  return (
    <WorkspaceContext.Provider
      value={{
        workspaces,
        activeWorkspace,
        switchWorkspace,
        isOrgMode: activeWorkspace !== null,
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
