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
import { StudentInviteSection } from '@/components/teacher/create-class/student-invite-section';
import { Card } from '@/components/ui/card';
import { MarkdownWithMath } from '@/components/content/markdown-with-math';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
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
  const [isInviteExpanded, setIsInviteExpanded] = useState(false);

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
        recap_markdown: '',
        error_detail: detail.pipelineErrorDetail ?? '',
        created_at: detail.createdAt ?? '',
        updated_at: detail.lastActivity ?? '',
      }
    );

    // Always fetch once to load fields not present in the detail hook (e.g., recap_markdown).
    void getClassCreationSessionDetail(sessionId)
      .then((next) => setSessionDetail(next))
      .catch(() => {
        // ignore transient failures
      });

    const shouldPoll = ['transcribing', 'structuring', 'prereq_extracting', 'prereq_teaching', 'recapping'].includes(detail.pipelineStatus ?? '');
    if (!shouldPoll) return;

    if (pollTimer.current) window.clearInterval(pollTimer.current);
    pollTimer.current = window.setInterval(async () => {
      try {
        const next = await getClassCreationSessionDetail(sessionId);
        setSessionDetail(next);

        if (!['transcribing', 'structuring', 'prereq_extracting', 'prereq_teaching', 'recapping'].includes(next.status)) {
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

  const sortedPrereqs = (prereqs ?? []).slice().sort((a, b) => a.order - b.order);
  const prereqListMarkdown =
    prereqs === null
      ? ''
      : sortedPrereqs.length
        ? sortedPrereqs.map((p) => `- ${p.order}. ${p.name}`).join('\n')
        : '—';

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
            <div className="flex flex-col gap-3" dir="rtl">
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

              <Accordion type="multiple" className="space-y-3">
                <AccordionItem value="step-1" className="border-b-0 rounded-2xl border border-border/60 bg-background/50 px-4">
                  <AccordionTrigger className="hover:no-underline">
                    <span className="text-sm font-bold">مرحله ۱: متن</span>
                  </AccordionTrigger>
                  <AccordionContent className="pt-2">
                    <div className="rounded-xl border border-border/60 bg-background/80 p-4 max-h-[45vh] overflow-y-auto">
                      <MarkdownWithMath markdown={sessionDetail?.transcript_markdown || detail.transcriptMarkdown || '—'} />
                    </div>
                  </AccordionContent>
                </AccordionItem>

                <AccordionItem value="step-2" className="border-b-0 rounded-2xl border border-border/60 bg-background/50 px-4">
                  <AccordionTrigger className="hover:no-underline">
                    <span className="text-sm font-bold">مرحله ۲: ساختار</span>
                  </AccordionTrigger>
                  <AccordionContent className="pt-2">
                    <div className="rounded-xl border border-border/60 bg-background/80 p-4 max-h-[45vh] overflow-y-auto">
                      <StructuredContentView structureJson={sessionDetail?.structure_json || detail.structureJson || ''} />
                    </div>
                  </AccordionContent>
                </AccordionItem>

                <AccordionItem value="step-3" className="border-b-0 rounded-2xl border border-border/60 bg-background/50 px-4">
                  <AccordionTrigger className="hover:no-underline">
                    <span className="text-sm font-bold">مرحله ۳: پیش‌نیازها</span>
                  </AccordionTrigger>
                  <AccordionContent className="pt-2">
                    <div className="rounded-xl border border-border/60 bg-background/80 p-4 max-h-[45vh] overflow-y-auto">
                      {prereqs === null ? (
                        <div className="text-xs text-muted-foreground">در حال بارگذاری…</div>
                      ) : (
                        <MarkdownWithMath markdown={prereqListMarkdown} />
                      )}
                    </div>
                  </AccordionContent>
                </AccordionItem>

                <AccordionItem value="step-4" className="border-b-0 rounded-2xl border border-border/60 bg-background/50 px-4">
                  <AccordionTrigger className="hover:no-underline">
                    <span className="text-sm font-bold">مرحله ۴: تدریس پیش‌نیازها</span>
                  </AccordionTrigger>
                  <AccordionContent className="pt-2">
                    <div className="rounded-xl border border-border/60 bg-background/80 p-4 max-h-[45vh] overflow-y-auto">
                      {prereqs === null ? (
                        <div className="text-xs text-muted-foreground">در حال بارگذاری…</div>
                      ) : sortedPrereqs.length === 0 ? (
                        <div className="text-xs text-muted-foreground">—</div>
                      ) : (
                        <div className="space-y-3">
                          {sortedPrereqs.map((p) => (
                            <div key={p.id} className="rounded-2xl border border-border/60 bg-background/70 p-4 space-y-2">
                              <div className="text-sm font-black">
                                {p.order}. {p.name}
                              </div>
                              {p.teaching_text?.trim() ? (
                                <MarkdownWithMath markdown={p.teaching_text} />
                              ) : (
                                <div className="text-xs text-muted-foreground">(متن تدریس هنوز ساخته نشده است.)</div>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </AccordionContent>
                </AccordionItem>

                <AccordionItem value="step-5" className="border-b-0 rounded-2xl border border-border/60 bg-background/50 px-4">
                  <AccordionTrigger className="hover:no-underline">
                    <span className="text-sm font-bold">مرحله ۵: جمع‌بندی</span>
                  </AccordionTrigger>
                  <AccordionContent className="pt-2">
                    <div className="rounded-xl border border-border/60 bg-background/80 p-4 max-h-[45vh] overflow-y-auto">
                      <MarkdownWithMath markdown={sessionDetail?.recap_markdown || '—'} />
                    </div>
                  </AccordionContent>
                </AccordionItem>
              </Accordion>
            </div>
          </Card>

          <ClassInfoCard description={detail.description} tags={detail.tags} objectives={detail.objectives} />
          <ClassChaptersCard classId={classId} chapters={detail.chapters || []} basePath="/teacher" />
          <ClassStudentsPreview
            classId={classId}
            students={students}
            basePath="/teacher"
            onAddClick={() => setIsInviteExpanded(true)}
          />
          <StudentInviteSection
            isExpanded={isInviteExpanded}
            onToggle={() => setIsInviteExpanded((p) => !p)}
            sessionId={Number(detail.id)}
          />
          <ClassAnnouncementsCard />
        </div>

        <div className="lg:col-span-1">
          <ClassStatsSidebar classDetail={detail} totalStudents={students.length} />
        </div>
      </div>
    </div>
  );
}
