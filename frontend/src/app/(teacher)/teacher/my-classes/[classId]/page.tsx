'use client';

import { use, useEffect, useRef, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { useTeacherClassDetail } from '@/hooks/use-teacher-class-detail';
import {
  ClassDetailHeader,
  ClassInfoCard,
  ClassChaptersCard,
  ClassStudentsPreview,
  ClassStatsSidebar,
  ClassAnnouncementsCard,
} from '@/components/teacher/class-detail';
import { Card } from '@/components/ui/card';
import { MarkdownWithMath } from '@/components/content/markdown-with-math';
import {
  getClassCreationSessionDetail,
  listClassPrerequisites,
  type ClassCreationSessionDetail,
  type ClassPrerequisite,
} from '@/services/classes-service';
import { StructuredContentView } from '@/components/teacher/class-detail/structured-content-view';

interface PageProps {
  params: Promise<{ classId: string }>;
}

export default function TeacherClassDetailPage({ params }: PageProps) {
  const { classId } = use(params);
  const { detail, students, isLoading, error } = useTeacherClassDetail(classId);

  const [sessionDetail, setSessionDetail] = useState<ClassCreationSessionDetail | null>(null);
  const [prereqs, setPrereqs] = useState<ClassPrerequisite[] | null>(null);
  const pollTimer = useRef<number | null>(null);

  useEffect(() => {
    if (!detail) return;

    const sessionId = Number(detail.id);
    if (!Number.isFinite(sessionId)) return;

    // Seed from initial detail fetch
    setSessionDetail((prev) =>
      prev ?? {
        id: sessionId,
        status: detail.pipelineStatus ?? '',
        title: detail.title,
        description: detail.description,
        source_mime_type: '',
        source_original_name: '',
        transcript_markdown: detail.transcriptMarkdown ?? '',
        structure_json: detail.structureJson ?? '',
        error_detail: detail.pipelineErrorDetail ?? '',
        created_at: detail.createdAt ?? '',
        updated_at: detail.lastActivity ?? '',
      }
    );

    const shouldPoll = ['transcribing', 'structuring', 'prereq_extracting', 'prereq_teaching'].includes(detail.pipelineStatus ?? '');
    if (!shouldPoll) return;

    if (pollTimer.current) window.clearInterval(pollTimer.current);
    pollTimer.current = window.setInterval(async () => {
      try {
        const next = await getClassCreationSessionDetail(sessionId);
        setSessionDetail(next);

        if (!['transcribing', 'structuring', 'prereq_extracting', 'prereq_teaching'].includes(next.status)) {
          if (pollTimer.current) {
            window.clearInterval(pollTimer.current);
            pollTimer.current = null;
          }
        }
      } catch {
        // ignore transient failures
      }
    }, 1500);

    return () => {
      if (pollTimer.current) {
        window.clearInterval(pollTimer.current);
        pollTimer.current = null;
      }
    };
  }, [detail]);

  useEffect(() => {
    const sessionId = Number(detail?.id);
    if (!Number.isFinite(sessionId)) return;

    let mounted = true;
    listClassPrerequisites(sessionId)
      .then((items) => {
        if (mounted) setPrereqs(items);
      })
      .catch(() => {
        if (mounted) setPrereqs([]);
      });

    return () => {
      mounted = false;
    };
  }, [detail?.id]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <p className="text-destructive">خطا در بارگذاری اطلاعات کلاس</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <ClassDetailHeader
        classId={classId}
        title={detail.title}
        category={detail.category}
        level={detail.level}
        status={detail.status}
        basePath="/teacher"
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <Card className="p-4 md:p-6 rounded-3xl border border-border/60">
            <div className="flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <h2 className="text-base md:text-lg font-black">خروجی پایپ‌لاین</h2>
                <span className="text-xs text-muted-foreground">
                  وضعیت: {sessionDetail?.status || detail.pipelineStatus || '—'}
                </span>
              </div>

              {(sessionDetail?.error_detail || detail.pipelineErrorDetail) && (
                <div className="text-xs text-destructive">
                  {sessionDetail?.error_detail || detail.pipelineErrorDetail}
                </div>
              )}

              <div className="grid grid-cols-1 gap-4">
                <div className="space-y-2">
                  <div className="text-sm font-bold">متن (مرحله ۱)</div>
                  <div className="rounded-xl border border-border/60 bg-background/80 p-4 max-h-[60vh] overflow-y-auto">
                    <MarkdownWithMath markdown={sessionDetail?.transcript_markdown || detail.transcriptMarkdown || ''} />
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="text-sm font-bold">ساختار (مرحله ۲)</div>
                  <div className="rounded-xl border border-border/60 bg-background/80 p-4 max-h-[70vh] overflow-y-auto">
                    <StructuredContentView structureJson={sessionDetail?.structure_json || detail.structureJson || ''} />
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="text-sm font-bold">پیش نیازها (مرحله ۳ و ۴)</div>

                  {prereqs === null ? (
                    <div className="text-xs text-muted-foreground">در حال بارگذاری…</div>
                  ) : prereqs.length === 0 ? (
                    <div className="text-xs text-muted-foreground">—</div>
                  ) : (
                    <div className="space-y-3">
                      {prereqs
                        .slice()
                        .sort((a, b) => a.order - b.order)
                        .map((p) => (
                          <div key={p.id} className="rounded-2xl border border-border/60 bg-background/80 p-4 space-y-2">
                            <div className="text-sm font-black">{p.order}. {p.name}</div>
                            {p.teaching_text?.trim() ? (
                              <div className="max-h-[45vh] overflow-y-auto pr-1">
                                <MarkdownWithMath markdown={p.teaching_text} />
                              </div>
                            ) : (
                              <div className="text-xs text-muted-foreground">(متن تدریس هنوز ساخته نشده است.)</div>
                            )}
                          </div>
                        ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </Card>

          <ClassInfoCard description={detail.description} tags={detail.tags} objectives={detail.objectives} />
          <ClassChaptersCard classId={classId} chapters={detail.chapters || []} basePath="/teacher" />
          <ClassStudentsPreview classId={classId} students={students} basePath="/teacher" />
          <ClassAnnouncementsCard />
        </div>

        <div className="lg:col-span-1">
          <ClassStatsSidebar classDetail={detail} totalStudents={students.length} />
        </div>
      </div>
    </div>
  );
}
