'use client';

import { ArrowLeft } from 'lucide-react';
import { Activity } from '@/types';

interface ActivityCardProps extends Activity {}

export const ActivityCard = ({ title, time, type, icon }: ActivityCardProps) => (
  <div className="group flex items-center justify-between bg-muted/30 p-4 rounded-2xl hover:bg-muted/50 border border-transparent hover:border-primary/20 transition-all duration-300 cursor-pointer">
    <div className="flex items-center gap-4">
      <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-primary/10 text-primary group-hover:bg-primary group-hover:text-primary-foreground transition-all duration-300">
        {icon}
      </div>
      <div>
        <h4 className="font-bold text-foreground group-hover:text-primary transition-colors">{title}</h4>
        <div className="flex items-center gap-2 text-xs text-muted-foreground mt-1">
          <span className="font-medium">{time}</span>
          <span className="w-1 h-1 rounded-full bg-border"></span>
          <span className="text-primary font-bold">{type}</span>
        </div>
      </div>
    </div>
    <div className="flex items-center justify-center w-8 h-8 rounded-full bg-background border border-border group-hover:border-primary/50 group-hover:text-primary transition-all duration-300 opacity-0 group-hover:opacity-100 -translate-x-2 group-hover:translate-x-0">
      <ArrowLeft className="h-4 w-4" />
    </div>
  </div>
);
