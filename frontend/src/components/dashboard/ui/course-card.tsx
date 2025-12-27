'use client';

import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ArrowLeft, Play } from 'lucide-react';
import Link from 'next/link';
import { Course } from '@/types';
import { TagBadge } from '@/components/ui/tag-badge';

interface CourseCardProps {
  course: Course;
}

export const CourseCard = ({ course }: CourseCardProps) => {
  const isFeatured = course.tags.includes('ریاضیات') || course.tags.includes('برنامه‌نویسی');
  return (
    <Card className="bg-card text-card-foreground overflow-hidden flex flex-col justify-between h-full rounded-2xl">
      <CardContent className="p-6">
        <div className="flex justify-start mb-4">
          {course.tags.map((tag) => (
            <TagBadge key={tag} tag={tag} />
          ))}
        </div>
        <h3 className="font-bold text-xl text-text-light mb-2">{course.title}</h3>
        <p className="text-text-muted text-sm leading-relaxed">{course.description}</p>
      </CardContent>
      <div className="px-6 pb-6">
        {isFeatured ? (
          <Button asChild className="w-full bg-primary hover:bg-primary/90 text-primary-foreground">
            <Link href="/learn/1">
              ادامه یادگیری <ArrowLeft className="mr-2 h-4 w-4" />
            </Link>
          </Button>
        ) : (
          <Button asChild className="w-full bg-secondary hover:bg-secondary/80 text-primary">
            <Link href="/learn/1">
              <Play className="h-4 w-4 ml-2 fill-current" /> شروع دوره
            </Link>
          </Button>
        )}
      </div>
    </Card>
  );
};
