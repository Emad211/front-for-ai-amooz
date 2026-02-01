'use client';

import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { List, Play, ArrowLeft } from 'lucide-react';
import Link from 'next/link';
import { Exam } from '@/types';
import { TagBadge } from '@/components/ui/tag-badge';

interface ExamCardProps {
  exam: Exam;
}

export const ExamCard = ({ exam }: ExamCardProps) => {
  const primaryTag = exam.tags?.[0] || 'آزمون';
  const examHref = `/exam/${exam.id}`;

  return (
    <Card className="group bg-card border-border/50 hover:border-primary/30 transition-all duration-300 overflow-hidden flex flex-col justify-between h-full rounded-3xl hover:shadow-2xl hover:shadow-primary/5">
      <CardContent className="p-6 md:p-8">
        <div className="flex justify-start mb-6">
          <TagBadge tag={primaryTag} />
        </div>
        <h3 className="font-black text-xl md:text-2xl text-foreground mb-3 group-hover:text-primary transition-colors">{exam.title}</h3>
        <p className="text-muted-foreground text-sm md:text-base leading-relaxed mb-6 font-medium">{exam.description}</p>
        <div className="flex items-center text-muted-foreground text-sm font-bold bg-muted/50 w-fit px-3 py-1.5 rounded-xl border border-border/50">
          <List className="ml-2 h-4 w-4 text-primary" />
          <span>{exam.questions} سوال</span>
        </div>
      </CardContent>
      <div className="px-6 md:px-8 pb-6 md:pb-8">
        <Button
          asChild
          className="w-full h-12 md:h-14 bg-primary hover:bg-primary/90 text-primary-foreground rounded-2xl font-bold text-base shadow-lg shadow-primary/20 transition-all group-hover:scale-[1.02]"
        >
          <Link href={examHref}>
            <Play className="h-5 w-5 ml-2 fill-current" /> شروع یادگیری
          </Link>
        </Button>
      </div>
    </Card>
  );
};
