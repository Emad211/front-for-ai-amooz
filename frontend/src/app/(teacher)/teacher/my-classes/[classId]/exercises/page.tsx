'use client';

import { use } from 'react';
import Link from 'next/link';
import { ArrowRight } from 'lucide-react';

import { ExerciseManager } from '@/components/teacher/exercises/exercise-manager';
import { Button } from '@/components/ui/button';

interface PageProps {
  params: Promise<{ classId: string }>;
}

export default function TeacherClassExercisesPage({ params }: PageProps) {
  const { classId } = use(params);
  const sessionId = Number(classId);

  return (
    <main dir="rtl" className="container mx-auto max-w-5xl px-4 py-6 md:py-8">
      <div className="mb-6 flex items-center justify-between gap-2">
        <h1 className="text-xl font-bold md:text-2xl">تمرین‌های کلاس</h1>
        <Button variant="ghost" asChild>
          <Link href={`/teacher/my-classes/${classId}`}>
            <ArrowRight className="ms-2 h-4 w-4" />
            بازگشت به کلاس
          </Link>
        </Button>
      </div>
      {Number.isFinite(sessionId) ? (
        <ExerciseManager sessionId={sessionId} />
      ) : (
        <p className="text-muted-foreground">شناسهٔ کلاس نامعتبر است.</p>
      )}
    </main>
  );
}
