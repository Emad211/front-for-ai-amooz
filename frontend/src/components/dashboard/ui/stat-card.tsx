'use client';

import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";

interface StatCardProps {
  title: string;
  value: string;
  subValue: string;
  icon?: React.ReactNode;
  tag?: string;
  progress?: number;
}

export const StatCard = ({ title, value, subValue, icon, tag, progress }: StatCardProps) => (
  <Card className="bg-card text-text-light flex-1 min-w-[220px]">
    <CardHeader className="flex flex-row items-center justify-between pb-2 text-text-muted">
      <h3 className="text-sm font-medium">{title}</h3>
      {tag && <div className="text-xs font-semibold px-2 py-0.5 rounded-full border border-primary text-primary">{tag}</div>}
    </CardHeader>
    <CardContent>
      <div className="flex items-center gap-4">
        {icon && <div className="bg-primary/10 p-3 rounded-md">{icon}</div>}
        <div className="flex-grow">
          <p className="text-3xl font-bold">{value}</p>
          <p className="text-xs text-text-muted">{subValue}</p>
        </div>
      </div>
      {progress !== undefined && (
        <div className="mt-4">
          <Progress value={progress} className="h-2 [&>div]:bg-primary" />
        </div>
      )}
    </CardContent>
  </Card>
);
