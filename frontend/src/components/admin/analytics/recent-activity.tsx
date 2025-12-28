'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { UserPlus, BookOpen, MessageSquare, Award } from 'lucide-react';
import { MOCK_RECENT_ACTIVITIES } from '@/constants/mock';

const ICON_MAP = {
  'user-plus': UserPlus,
  'book': BookOpen,
  'message': MessageSquare,
  'award': Award,
};

export function RecentActivity() {
  return (
    <Card className="bg-card border-border/60 lg:col-span-1">
      <CardHeader>
        <CardTitle className="text-lg font-bold">فعالیت‌های اخیر</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-6">
          {MOCK_RECENT_ACTIVITIES.map((activity) => {
            const Icon = ICON_MAP[activity.icon as keyof typeof ICON_MAP];
            return (
              <div key={activity.id} className="flex items-start gap-4">
                <div className={`p-2 rounded-lg ${activity.bg}`}>
                  <Icon className={`w-4 h-4 ${activity.color}`} />
                </div>
                <div className="flex-1 space-y-1">
                  <p className="text-sm font-medium text-foreground">
                    <span className="font-bold">{activity.user}</span> {activity.action}
                  </p>
                  <p className="text-xs text-muted-foreground">{activity.time}</p>
                </div>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
