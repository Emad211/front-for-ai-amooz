'use client';

import { Building2, ChevronDown, User } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { useWorkspace } from '@/hooks/use-workspace';

export function WorkspaceSwitcher() {
  const { workspaces, activeWorkspace, switchWorkspace, isLoading, personalAllowed } = useWorkspace();

  // Total selectable spaces = personal (if allowed) + each org. With one or none
  // there's nothing to switch between, so hide the switcher entirely.
  const totalSpaces = (personalAllowed ? 1 : 0) + workspaces.length;
  if (!isLoading && totalSpaces <= 1) return null;

  return (
    <DropdownMenu dir="rtl">
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          className="w-full justify-start gap-2 px-3 py-2.5 h-auto rounded-xl text-sm font-bold"
        >
          {activeWorkspace ? (
            <>
              {activeWorkspace.logo ? (
                <img
                  src={activeWorkspace.logo}
                  alt={activeWorkspace.name}
                  className="w-5 h-5 rounded object-cover"
                />
              ) : (
                <Building2 className="w-5 h-5 text-primary" />
              )}
              <span className="flex-1 text-right truncate min-w-0">{activeWorkspace.name}</span>
            </>
          ) : (
            <>
              <User className="w-5 h-5 text-muted-foreground" />
              <span className="flex-1 text-right">فضای شخصی</span>
            </>
          )}
          <ChevronDown className="w-4 h-4 text-muted-foreground" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-56 max-w-[calc(100vw-2rem)]">
        {personalAllowed && (
          <DropdownMenuItem
            onClick={() => switchWorkspace(null)}
            className={cn('gap-2 cursor-pointer', !activeWorkspace && 'bg-muted')}
          >
            <User className="w-4 h-4" />
            فضای شخصی
          </DropdownMenuItem>
        )}
        {personalAllowed && workspaces.length > 0 && <DropdownMenuSeparator />}
        {workspaces.map((ws) => (
          <DropdownMenuItem
            key={ws.id}
            onClick={() => switchWorkspace(ws)}
            className={cn('gap-2 cursor-pointer', activeWorkspace?.id === ws.id && 'bg-muted')}
          >
            {ws.logo ? (
              <img src={ws.logo} alt={ws.name} className="w-4 h-4 rounded object-cover" />
            ) : (
              <Building2 className="w-4 h-4" />
            )}
            <span className="flex-1 truncate min-w-0">{ws.name}</span>
            <span className="text-[10px] text-muted-foreground shrink-0">{ws.orgRoleDisplay}</span>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
