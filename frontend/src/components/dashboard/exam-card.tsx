'use client';

import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { List, Play, ArrowLeft } from 'lucide-react';
import Link from 'next/link';

interface Exam {
  id: number;
  title: string;
  description: string;
  tags: string[];
  questions: number;
}

interface ExamCardProps {
  exam: Exam;
}

export const ExamCard = ({ exam }: ExamCardProps) => {
  const isInProgress = exam.tags.includes('ریاضیات') || exam.tags.includes('برنامه نویسی');
  const isDiscreteMath = exam.id === 1;

  return (
    <Card className="bg-card text-card-foreground overflow-hidden flex flex-col justify-between h-full rounded-2xl">
      <CardContent className="p-6">
        <div className="flex justify-start mb-4">
          <Badge
            variant="secondary"
            className={`bg-opacity-20 text-sm font-normal ${
              exam.tags[0] === 'هوش مصنوعی'
                ? 'bg-green-500/20 text-green-400 border-green-500/30'
                : exam.tags[0] === 'ریاضیات'
                ? 'bg-purple-500/20 text-purple-400 border-purple-500/30'
                : exam.tags[0] === 'فیزیک'
                ? 'bg-blue-500/20 text-blue-400 border-blue-500/30'
                : exam.tags[0] === 'برنامه نویسی'
                ? 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30'
                : exam.tags[0] === 'زبان'
                ? 'bg-pink-500/20 text-pink-400 border-pink-500/30'
                : exam.tags[0] === 'آمار'
                ? 'bg-purple-500/20 text-purple-400 border-purple-500/30'
                : 'bg-gray-500/20 text-gray-400 border-gray-500/30'
            } border mr-2`}
          >
            {exam.tags[0]}
          </Badge>
        </div>
        <h3 className="font-bold text-xl text-text-light mb-2">{exam.title}</h3>
        <p className="text-text-muted text-sm leading-relaxed mb-4">{exam.description}</p>
        <div className="flex items-center text-text-muted text-sm">
          <List className="ml-2 h-4 w-4" />
          <span>{exam.questions} سوال</span>
        </div>
      </CardContent>
      <div className="px-6 pb-6">
        {isInProgress ? (
          <Button asChild className="w-full bg-primary hover:bg-primary/90 text-primary-foreground rounded-lg">
            <Link href={isDiscreteMath ? '/exam/1' : '#'}>
              ادامه یادگیری <ArrowLeft className="mr-2 h-4 w-4" />
            </Link>
          </Button>
        ) : (
          <Button
            asChild
            variant="secondary"
            className="w-full bg-secondary hover:bg-secondary/80 text-primary rounded-lg"
          >
            <Link href="#">
              <Play className="h-4 w-4 ml-2 fill-current" /> شروع یادگیری
            </Link>
          </Button>
        )}
      </div>
    </Card>
  );
};
