'use client';

import { use } from 'react';
import { useSearchParams } from 'next/navigation';

import { ExerciseSolver } from '@/components/dashboard/exercises/exercise-solver';

interface PageProps {
  params: Promise<{ exerciseId: string }>;
}

export default function StudentExerciseSolvePage({ params }: PageProps) {
  const { exerciseId } = use(params);
  const search = useSearchParams();
  const sessionId = Number(search.get('session'));
  const exId = Number(exerciseId);

  return (
    <main dir="rtl" className="container mx-auto max-w-5xl px-4 py-6 md:py-8">
      {Number.isFinite(sessionId) && Number.isFinite(exId) ? (
        <ExerciseSolver sessionId={sessionId} exerciseId={exId} />
      ) : (
        <p className="text-muted-foreground">شناسهٔ تمرین یا کلاس نامعتبر است.</p>
      )}
    </main>
  );
}
