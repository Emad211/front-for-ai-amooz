'use client';

import { use, useEffect, useRef, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { useTeacherClassDetail as useClassDetail } from '@/hooks/use-teacher-class-detail';
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

export default function ClassDetailPage({ params }: PageProps) {
  const { classId } = use(params);
  const { detail: classDetail, students, isLoading, error } = useClassDetail(classId);

  const [sessionDetail, setSessionDetail] = useState<ClassCreationSessionDetail | null>(null);
  const [prereqs, setPrereqs] = useState<ClassPrerequisite[] | null>(null);
  const pollTimer = useRef<number | null>(null);

  useEffect(() => {
    if (!classDetail) return;

    const sessionId = Number(classDetail.id);
    if (!Number.isFinite(sessionId)) return;

    setSessionDetail((prev) =>
      prev ?? {
        id: sessionId,
        status: classDetail.pipelineStatus ?? '',
        title: classDetail.title,
        description: classDetail.description,
        source_mime_type: '',
        source_original_name: '',
        transcript_markdown: classDetail.transcriptMarkdown ?? '',
        structure_json: classDetail.structureJson ?? '',
        error_detail: classDetail.pipelineErrorDetail ?? '',
        created_at: classDetail.createdAt ?? '',
        updated_at: classDetail.lastActivity ?? '',
      }
    );

    const shouldPoll = ['transcribing', 'structuring', 'prereq_extracting', 'prereq_teaching'].includes(classDetail.pipelineStatus ?? '');
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
  }, [classDetail]);

  useEffect(() => {
    const sessionId = Number(classDetail?.id);
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
  }, [classDetail?.id]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error || !classDetail) {
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
        title={classDetail.title}
        category={classDetail.category}
        level={classDetail.level}
        status={classDetail.status}
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          <Card className="p-4 md:p-6 rounded-3xl border border-border/60">
            <div className="flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <h2 className="text-base md:text-lg font-black">خروجی پایپ‌لاین</h2>
                <span className="text-xs text-muted-foreground">
                  وضعیت: {sessionDetail?.status || classDetail.pipelineStatus || '—'}
                </span>
              </div>

              {(sessionDetail?.error_detail || classDetail.pipelineErrorDetail) && (
                <div className="text-xs text-destructive">
                  {sessionDetail?.error_detail || classDetail.pipelineErrorDetail}
                </div>
              )}

              <div className="grid grid-cols-1 gap-4">
                <div className="space-y-2">
                  <div className="text-sm font-bold">متن (مرحله ۱)</div>
                  <div className="rounded-xl border border-border/60 bg-background/80 p-4 max-h-[60vh] overflow-y-auto">
                    <MarkdownWithMath markdown={sessionDetail?.transcript_markdown || classDetail.transcriptMarkdown || ''} />
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="text-sm font-bold">ساختار (مرحله ۲)</div>
                  <div className="rounded-xl border border-border/60 bg-background/80 p-4 max-h-[70vh] overflow-y-auto">
                    <StructuredContentView structureJson={sessionDetail?.structure_json || classDetail.structureJson || ''} />
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

          <ClassInfoCard 
            description={classDetail.description}
            tags={classDetail.tags}
          />
          
          <ClassChaptersCard 
            classId={classId}
            chapters={classDetail.chapters || []}
          />
          
          <ClassStudentsPreview 
            classId={classId}
            students={students}
          />
          
          <ClassAnnouncementsCard />
        </div>

        {/* Sidebar */}
        <div className="lg:col-span-1">
          <ClassStatsSidebar 
            classDetail={classDetail}
            totalStudents={students.length}
          />
        </div>
      </div>
    </div>
  );
}
