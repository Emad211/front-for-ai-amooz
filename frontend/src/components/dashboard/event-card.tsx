'use client';

import { ArrowLeft } from 'lucide-react';

interface EventCardProps {
  title: string;
  status: string;
  icon: React.ReactNode;
  date: string;
  month: string;
}

export const EventCard = ({ title, status, icon, date, month }: EventCardProps) => (
  <div className="flex items-center justify-between bg-card/50 p-4 rounded-lg hover:bg-border transition-colors cursor-pointer">
    <div className="flex items-center gap-4">
      <div className="flex flex-col items-center justify-center bg-primary/10 text-primary rounded-lg w-12 h-12 flex-shrink-0">
        <span className="text-sm font-bold">{date}</span>
        <span className="text-xs">{month}</span>
      </div>
      <div>
        <h4 className="font-semibold text-text-light">{title}</h4>
        <p className="text-xs text-text-muted flex items-center gap-1.5">
          {icon}
          <span>{status}</span>
        </p>
      </div>
    </div>
    <div className="flex items-center justify-center w-8 h-8 rounded-full bg-primary/10 text-primary">
      <ArrowLeft className="h-4 w-4" />
    </div>
  </div>
);
