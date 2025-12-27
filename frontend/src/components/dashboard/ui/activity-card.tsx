'use client';

import { ArrowLeft } from 'lucide-react';
import { Activity } from '@/types';

interface ActivityCardProps extends Activity {}

export const ActivityCard = ({ title, time, type, icon }: ActivityCardProps) => (
  <div className="flex items-center justify-between bg-card/50 p-4 rounded-lg hover:bg-border transition-colors cursor-pointer">
    <div className="flex items-center gap-4">
      <div className="flex items-center justify-center w-8 h-8 rounded-full bg-primary/10 text-primary">{icon}</div>
      <div>
        <h4 className="font-semibold text-text-light">{title}</h4>
        <div className="flex items-center gap-2 text-xs text-text-muted">
          <span>{time}</span>
          <span className="text-primary">•</span>
          <span className="text-primary font-medium">{type}</span>
        </div>
      </div>
    </div>
    <div className="flex items-center justify-center w-8 h-8 rounded-full bg-primary/10 text-primary">
      <ArrowLeft className="h-4 w-4" />
    </div>
  </div>
);
