'use client';

import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ArrowLeft, Play } from 'lucide-react';
import Link from 'next/link';
import { Course } from '@/types';
import { TagBadge } from '@/components/ui/tag-badge';
import React from 'react';

interface CourseCardProps {
  course: Course;
}

export const CourseCard = ({ course }: CourseCardProps) => {
  const courseId = encodeURIComponent(String(course.id));

  const [hasVisited, setHasVisited] = React.useState(false);

  React.useEffect(() => {
    if (typeof window === 'undefined') return;
    const key = `ai_amooz_course_visited_${String(course.id)}`;
    setHasVisited(window.localStorage.getItem(key) === '1');
  }, [course.id]);

  const progress = Number(course.progress ?? 0);
  const isContinue = hasVisited || (Number.isFinite(progress) && progress > 0);

  return (
    <Card className="group bg-card border-border/50 hover:border-primary/30 transition-all duration-300 overflow-hidden flex flex-col justify-between h-full rounded-3xl hover:shadow-2xl hover:shadow-primary/5">
      <CardContent className="p-6 md:p-8">
        <div className="flex justify-start mb-6 gap-2">
          {course.tags.map((tag) => (
            <TagBadge key={tag} tag={tag} />
          ))}
        </div>
        <h3 className="font-black text-xl md:text-2xl text-foreground mb-3 group-hover:text-primary transition-colors">{course.title}</h3>
        <p className="text-muted-foreground text-sm md:text-base leading-relaxed font-medium">{course.description}</p>
      </CardContent>
      <div className="px-6 md:px-8 pb-6 md:pb-8">
        {isContinue ? (
          <Button
            asChild
            className="w-full h-12 md:h-14 bg-primary hover:bg-primary/90 text-primary-foreground rounded-2xl font-bold text-base shadow-lg shadow-primary/20 transition-all group-hover:scale-[1.02]"
          >
            <Link href={`/learn/${courseId}`}>
              ادامه یادگیری <ArrowLeft className="mr-2 h-5 w-5" />
            </Link>
          </Button>
        ) : (
          <Button
            asChild
            variant="secondary"
            className="w-full h-12 md:h-14 bg-secondary/50 hover:bg-secondary text-primary rounded-2xl font-bold text-base transition-all group-hover:scale-[1.02]"
          >
            <Link href={`/learn/${courseId}`}>
              <Play className="h-5 w-5 ml-2 fill-current" /> شروع دوره
            </Link>
          </Button>
        )}
      </div>
    </Card>
  );
};
