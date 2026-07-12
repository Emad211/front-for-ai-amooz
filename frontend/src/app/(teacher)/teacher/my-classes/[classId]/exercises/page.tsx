'use client';

import { use, useEffect, useState } from 'react';
import Link from 'next/link';
import { ArrowRight } from 'lucide-react';

import { ClassWorkspaceNav } from '@/components/teacher/class-detail';
import { ExerciseManager } from '@/components/teacher/exercises/exercise-manager';
import { Button } from '@/components/ui/button';
import {
  getClassCreationSessionDetail,
  type PendingExerciseSnapshot,
} from '@/services/classes-service';

interface PageProps {
  params: Promise<{ classId: string }>;
}

export default function TeacherClassExercisesPage({ params }: PageProps) {
  const { classId } = use(params);
  const sessionId = Number(classId);
  const [pendingExercises, setPendingExercises] = useState<PendingExerciseSnapshot[]>([]);

  useEffect(() => {
    if (!Number.isFinite(sessionId)) return;

    let mounted = true;
    getClassCreationSessionDetail(sessionId)
      .then((detail) => {
        if (mounted) setPendingExercises(detail.pendingExercises ?? []);
      })
      .catch(() => {
        if (mounted) setPendingExercises([]);
      });

    return () => {
      mounted = false;
    };
  }, [sessionId]);

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
      <ClassWorkspaceNav
        classId={classId}
        basePath="/teacher"
        className="mb-6"
        pendingExercises={pendingExercises}
      />
      {Number.isFinite(sessionId) ? (
        <ExerciseManager sessionId={sessionId} />
      ) : (
        <p className="text-muted-foreground">شناسهٔ کلاس نامعتبر است.</p>
      )}
    </main>
  );
}
