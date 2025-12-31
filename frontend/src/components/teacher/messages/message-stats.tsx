'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

interface MessageStatsProps {
  totalRecipients?: number;
  selectedCount?: number;
}

export function MessageStats({ totalRecipients, selectedCount }: MessageStatsProps) {
  return (
    <Card>
      <CardHeader className="text-start">
        <CardTitle className="text-lg">آمار پیام</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {totalRecipients !== undefined && (
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">کل مخاطبین</span>
            <Badge variant="secondary">{totalRecipients}</Badge>
          </div>
        )}
        {selectedCount !== undefined && (
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">گیرندگان انتخاب شده</span>
            <Badge variant="default" className="bg-primary/10 text-primary border-primary/20">
              {selectedCount}
            </Badge>
          </div>
        )}
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">پیام‌های امروز</span>
          <Badge variant="secondary">۱۲</Badge>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">نرخ بازدید</span>
          <Badge variant="outline" className="text-green-600 bg-green-50 border-green-200">۸۵٪</Badge>
        </div>
      </CardContent>
    </Card>
  );
}
