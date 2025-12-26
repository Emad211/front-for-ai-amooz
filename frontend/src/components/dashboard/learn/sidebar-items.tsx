'use client';

import React from 'react';
import { cn } from '@/lib/utils';

interface SidebarItemProps {
  icon: React.ReactElement;
  title: string;
  disabled?: boolean;
}

export const SidebarItem = ({ icon, title, disabled = false }: SidebarItemProps) => (
  <div className={cn('group', disabled && 'cursor-not-allowed text-muted-foreground/40')}>
    <div
      className={cn(
        'flex items-center justify-between p-3 rounded-xl cursor-pointer transition-all',
        disabled
          ? ''
          : 'text-muted-foreground hover:bg-secondary/30 hover:text-foreground border border-transparent hover:border-border/30'
      )}
    >
      <div className="flex items-center gap-3">
        {React.cloneElement(icon as React.ReactElement<{ className?: string }>, {
          className: cn('h-5 w-5', disabled ? 'text-muted-foreground/40' : 'text-muted-foreground'),
        })}
        <span className="text-base font-medium">{title}</span>
      </div>
    </div>
  </div>
);

interface SubmenuItemProps {
  icon: React.ReactElement;
  title: string;
  active?: boolean;
  special?: boolean;
}

export const SubmenuItem = ({ icon, title, active = false, special = false }: SubmenuItemProps) => (
  <div
    className={cn(
      'flex items-center gap-3 p-2 pr-4 rounded-lg cursor-pointer',
      active ? 'text-foreground' : 'text-muted-foreground hover:text-foreground hover:bg-foreground/5',
      special && 'text-green-500'
    )}
  >
    {React.cloneElement(icon as React.ReactElement<{ className?: string }>, { className: cn('h-4 w-4', active ? 'text-primary' : 'text-current') })}
    <span className={cn('text-sm', active && 'font-bold')}>{title}</span>
  </div>
);
