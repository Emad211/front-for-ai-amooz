'use client';

import { ArrowLeft } from 'lucide-react';
import { Event } from '@/types';

interface EventCardProps extends Event {}

export const EventCard = ({ title, status, icon, date, month }: EventCardProps) => (
  <div className="group flex items-center justify-between bg-muted/30 p-4 rounded-2xl hover:bg-muted/50 border border-transparent hover:border-primary/20 transition-all duration-300 cursor-pointer">
    <div className="flex items-center gap-4">
      <div className="flex flex-col items-center justify-center bg-primary/10 text-primary rounded-xl w-14 h-14 flex-shrink-0 border border-primary/20 group-hover:bg-primary group-hover:text-primary-foreground transition-all duration-300">
        <span className="text-lg font-black leading-none">{date}</span>
        <span className="text-[10px] font-bold uppercase mt-1">{month}</span>
      </div>
      <div>
        <h4 className="font-bold text-foreground group-hover:text-primary transition-colors">{title}</h4>
        <p className="text-xs text-muted-foreground flex items-center gap-1.5 mt-1.5">
          <span className="p-1 bg-background rounded-md border border-border group-hover:border-primary/30 transition-colors">
            {icon}
          </span>
          <span className="font-medium">{status}</span>
        </p>
      </div>
    </div>
    <div className="flex items-center justify-center w-8 h-8 rounded-full bg-background border border-border group-hover:border-primary/50 group-hover:text-primary transition-all duration-300 opacity-0 group-hover:opacity-100 -translate-x-2 group-hover:translate-x-0">
      <ArrowLeft className="h-4 w-4" />
    </div>
  </div>
);
