'use client';

/** Student report card (overall or per-course) — averages + per-exercise rows. */
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { type ReportCard } from '@/services/exercises-service';

export function ExerciseReportCard({ data, title }: { data: ReportCard; title: string }) {
  return (
    <Card dir="rtl">
      <CardHeader>
        <CardTitle className="flex items-center justify-between text-base">
          <span>{title}</span>
          {data.average != null && (
            <Badge variant="default">میانگین: {data.average}٪</Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {data.exercises.length === 0 ? (
          <p className="text-sm text-muted-foreground">هنوز تمرینِ نمره‌دهی‌شده‌ای ندارید.</p>
        ) : (
          data.exercises.map((row) => (
            <div key={row.exerciseId} className="space-y-1">
              <div className="flex items-center justify-between text-sm">
                <span>{row.exerciseTitle}</span>
                <span className="text-muted-foreground">
                  {row.scorePoints} از {row.maxPoints} ({row.percent}٪)
                </span>
              </div>
              <Progress value={row.percent} />
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}
