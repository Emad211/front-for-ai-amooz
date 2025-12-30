'use client';

import Link from 'next/link';
import { Edit, Video, FileText, HelpCircle, ClipboardList } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import type { ClassChapter } from '@/types';

interface ClassChaptersCardProps {
  classId: string;
  chapters: ClassChapter[];
}

const lessonTypeIcon: Record<string, React.ReactNode> = {
  video: <Video className="h-4 w-4" />,
  text: <FileText className="h-4 w-4" />,
  quiz: <HelpCircle className="h-4 w-4" />,
  assignment: <ClipboardList className="h-4 w-4" />,
};

export function ClassChaptersCard({ classId, chapters }: ClassChaptersCardProps) {
  const totalLessons = chapters.reduce((acc, ch) => acc + ch.lessons.length, 0);
  const publishedLessons = chapters.reduce(
    (acc, ch) => acc + ch.lessons.filter(l => l.isPublished).length, 
    0
  );

  return (
    <Card>
      <CardHeader className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div>
          <CardTitle className="text-base sm:text-lg">سرفصل‌ها و دروس</CardTitle>
          <CardDescription className="text-xs sm:text-sm">{publishedLessons} از {totalLessons} درس منتشر شده</CardDescription>
        </div>
        <Button variant="outline" size="sm" asChild>
          <Link href={`/admin/my-classes/${classId}/edit`}>
            <Edit className="h-4 w-4 sm:ml-2" />
            <span className="hidden sm:inline">ویرایش</span>
          </Link>
        </Button>
      </CardHeader>
      <CardContent className="space-y-4">
        {chapters.map((chapter, index) => (
          <div key={chapter.id} className="border rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <h4 className="font-semibold">فصل {index + 1}: {chapter.title}</h4>
              <span className="text-xs text-muted-foreground">{chapter.lessons.length} درس</span>
            </div>
            <div className="space-y-2">
              {chapter.lessons.map(lesson => (
                <div key={lesson.id} className="flex items-center justify-between p-2 rounded-lg bg-muted/50 text-sm">
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground">{lessonTypeIcon[lesson.type]}</span>
                    <span>{lesson.title}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground">{lesson.duration}</span>
                    {lesson.isPublished ? (
                      <Badge variant="outline" className="text-[10px] bg-primary/10 text-primary">منتشر شده</Badge>
                    ) : (
                      <Badge variant="outline" className="text-[10px] bg-muted text-muted-foreground">پیش‌نویس</Badge>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
