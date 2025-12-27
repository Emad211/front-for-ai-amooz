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
  <Card className="bg-card border-border/50 hover:border-primary/30 transition-all duration-300 group overflow-hidden relative">
    {/* Subtle background glow on hover */}
    <div className="absolute -right-8 -top-8 w-24 h-24 bg-primary/5 rounded-full blur-2xl group-hover:bg-primary/10 transition-colors"></div>
    
    <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
      <h3 className="text-sm font-bold text-muted-foreground">{title}</h3>
      {tag && (
        <div className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-primary/10 border border-primary/20 text-primary">
          {tag}
        </div>
      )}
    </CardHeader>
    <CardContent>
      <div className="flex items-center gap-4">
        {icon && (
          <div className="bg-primary/10 p-3 rounded-xl text-primary group-hover:scale-110 transition-transform duration-300">
            {icon}
          </div>
        )}
        <div className="flex-grow">
          <p className="text-3xl font-black text-foreground tracking-tight">{value}</p>
          <p className="text-xs text-muted-foreground font-medium mt-0.5">{subValue}</p>
        </div>
      </div>
      {progress !== undefined && (
        <div className="mt-5 space-y-1.5">
          <div className="flex justify-between text-[10px] font-bold text-muted-foreground">
            <span>میزان پیشرفت</span>
            <span>{progress}٪</span>
          </div>
          <Progress value={progress} className="h-1.5 bg-muted [&>div]:bg-primary shadow-sm" />
        </div>
      )}
    </CardContent>
  </Card>
);
