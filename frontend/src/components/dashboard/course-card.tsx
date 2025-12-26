'use client';

import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ArrowLeft, Play } from 'lucide-react';
import Link from 'next/link';

interface Course {
  id: number;
  title: string;
  description: string;
  tags: string[];
}

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
            <Badge
              key={tag}
              variant="secondary"
              className={`bg-opacity-20 text-sm font-normal ${
                tag === 'هوش مصنوعی'
                  ? 'bg-green-500/20 text-green-400 border-green-500/30'
                  : tag === 'ریاضیات'
                  ? 'bg-purple-500/20 text-purple-400 border-purple-500/30'
                  : tag === 'فیزیک'
                  ? 'bg-blue-500/20 text-blue-400 border-blue-500/30'
                  : tag === 'برنامه‌نویسی'
                  ? 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30'
                  : tag === 'زبان'
                  ? 'bg-pink-500/20 text-pink-400 border-pink-500/30'
                  : tag === 'ادبیات'
                  ? 'bg-purple-500/20 text-purple-400 border-purple-500/30'
                  : 'bg-gray-500/20 text-gray-400 border-gray-500/30'
              } border mr-2`}
            >
              {tag}
            </Badge>
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
