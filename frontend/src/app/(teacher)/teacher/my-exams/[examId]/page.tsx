'use client';

import { use, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { Loader2, ArrowRight, CheckCircle, Users, FileQuestion, Calendar, Clock, AlertCircle, Edit3 } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { MarkdownWithMath } from '@/components/content/markdown-with-math';
import { StudentInviteSection } from '@/components/teacher/create-class/student-invite-section';
import { ClassAnnouncementsCard } from '@/components/teacher/class-detail';
import {
  fetchExamPrepSession,
  publishExamPrepSession,
  type ExamPrepSessionDetail,
  listExamPrepInvites,
  type ClassInvite,
} from '@/services/classes-service';
import { formatDistanceToNow } from 'date-fns';
import { faIR } from 'date-fns/locale';
import { formatPersianDate, formatPersianDateTime } from '@/lib/date-utils';
import { toast } from 'sonner';

interface PageProps {
  params: Promise<{ examId: string }>;
}

const statusLabels: Record<string, string> = {
  pending: 'در انتظار',
  exam_transcribing: 'در حال رونویسی',
  exam_transcribed: 'رونویسی شده',
  exam_structuring: 'در حال استخراج سوالات',
  exam_structured: 'تکمیل شده',
  failed: 'خطا',
};

export default function TeacherExamDetailPage({ params }: PageProps) {
  const { examId } = use(params);
  const router = useRouter();

  const [examPrep, setExamPrep] = useState<ExamPrepSessionDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isPublishing, setIsPublishing] = useState(false);
  const [isInviteExpanded, setIsInviteExpanded] = useState(false);
  const [invites, setInvites] = useState<ClassInvite[]>([]);
  const pollTimer = useRef<number | null>(null);

  useEffect(() => {
    const sessionId = Number(examId);
    if (!Number.isFinite(sessionId)) {
      setError('شناسه آزمون نامعتبر است');
      setIsLoading(false);
      return;
    }

    const fetchData = async () => {
      try {
        const data = await fetchExamPrepSession(sessionId);
        setExamPrep(data);
        setError(null);

        // Fetch invites
        try {
          const inviteData = await listExamPrepInvites(sessionId);
          setInvites(inviteData);
        } catch {
          // Ignore invite fetch errors
        }

        // Start polling if processing
        if (['transcribing', 'qa_extracting'].includes(data.status)) {
          if (!pollTimer.current) {
            pollTimer.current = window.setInterval(async () => {
              try {
                const updated = await fetchExamPrepSession(sessionId);
                setExamPrep(updated);

                if (!['transcribing', 'qa_extracting'].includes(updated.status)) {
                  if (pollTimer.current) {
                    window.clearInterval(pollTimer.current);
                    pollTimer.current = null;
                  }
                }
              } catch {
                // Ignore polling errors
              }
            }, 2000);
          }
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'خطا در دریافت اطلاعات آزمون');
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();

    return () => {
      if (pollTimer.current) {
        window.clearInterval(pollTimer.current);
        pollTimer.current = null;
      }
    };
  }, [examId]);

  const handlePublish = async () => {
    if (!examPrep) return;

    setIsPublishing(true);
    try {
      const updated = await publishExamPrepSession(examPrep.id);
      setExamPrep(updated);
      toast.success('آزمون با موفقیت منتشر شد');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در انتشار آزمون');
    } finally {
      setIsPublishing(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error || !examPrep) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
        <AlertCircle className="h-12 w-12 text-destructive" />
        <p className="text-destructive">{error || 'خطا در بارگذاری اطلاعات آزمون'}</p>
        <Button variant="outline" onClick={() => router.back()}>
          بازگشت
        </Button>
      </div>
    );
  }

  const questions = examPrep.exam_prep_data?.exam_prep?.questions ?? [];
  const isProcessing = ['exam_transcribing', 'exam_structuring'].includes(examPrep.status);
  const canPublish = examPrep.status === 'exam_structured' && !examPrep.is_published && questions.length > 0;

  const getStatusBadge = () => {
    if (examPrep.is_published) {
      return <Badge className="bg-emerald-500/10 text-emerald-600 border-emerald-500/20">منتشر شده</Badge>;
    }
    if (isProcessing) {
      return <Badge className="bg-amber-500/10 text-amber-600 border-amber-500/20">{statusLabels[examPrep.status]}</Badge>;
    }
    if (examPrep.status === 'failed') {
      return <Badge className="bg-red-500/10 text-red-600 border-red-500/20">خطا</Badge>;
    }
    return <Badge variant="outline">{statusLabels[examPrep.status] || examPrep.status}</Badge>;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3 sm:gap-4">
          <Button variant="ghost" size="icon" onClick={() => router.back()} className="rounded-full shrink-0">
            <ArrowRight className="h-5 w-5" />
          </Button>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-1.5 sm:gap-2 mb-1">
              {getStatusBadge()}
              {examPrep.level && <Badge variant="outline">{examPrep.level}</Badge>}
            </div>
            <h1 className="text-xl sm:text-2xl font-bold truncate">{examPrep.title}</h1>
          </div>
        </div>
        <div className="flex items-center gap-2 mr-10 sm:mr-0">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsInviteExpanded(!isInviteExpanded)}
          >
            <Users className="h-4 w-4 sm:ml-2" />
            <span className="hidden sm:inline">دعوت دانش‌آموزان</span>
          </Button>
          {!isProcessing && (
            <Button variant="outline" size="sm" asChild>
              <Link href={`/teacher/my-exams/${examId}/edit`}>
                <Edit3 className="h-4 w-4 sm:ml-2" />
                <span className="hidden sm:inline">ویرایش</span>
              </Link>
            </Button>
          )}
          {canPublish && (
            <Button size="sm" onClick={handlePublish} disabled={isPublishing}>
              {isPublishing ? (
                <Loader2 className="h-4 w-4 animate-spin sm:ml-2" />
              ) : (
                <CheckCircle className="h-4 w-4 sm:ml-2" />
              )}
              <span className="hidden sm:inline">انتشار آزمون</span>
            </Button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Pipeline Output */}
          <Card className="p-4 md:p-6 rounded-3xl border border-border/60">
            <div className="flex flex-col gap-3" dir="rtl">
              <div className="flex items-center justify-between">
                <h2 className="text-base md:text-lg font-black">خروجی پایپ‌لاین</h2>
                <span className="text-xs text-muted-foreground">
                  وضعیت: {statusLabels[examPrep.status] || examPrep.status}
                </span>
              </div>

              {examPrep.error_detail && (
                <div className="text-xs text-destructive p-3 bg-destructive/10 rounded-xl">
                  {examPrep.error_detail}
                </div>
              )}

              {isProcessing && (
                <div className="flex items-center gap-2 p-3 bg-amber-500/10 rounded-xl">
                  <Loader2 className="h-4 w-4 animate-spin text-amber-600" />
                  <span className="text-sm text-amber-600">در حال پردازش... لطفا صبر کنید</span>
                </div>
              )}

              <Accordion type="multiple" className="space-y-3">
                <AccordionItem value="step-1" className="border-b-0 rounded-2xl border border-border/60 bg-background/50 px-4">
                  <AccordionTrigger className="hover:no-underline">
                    <span className="text-sm font-bold">مرحله ۱: متن</span>
                  </AccordionTrigger>
                  <AccordionContent className="pt-2">
                    <div className="rounded-xl border border-border/60 bg-background/80 p-4 max-h-[45vh] overflow-y-auto">
                      <MarkdownWithMath markdown={examPrep.transcript_markdown || '—'} />
                    </div>
                  </AccordionContent>
                </AccordionItem>

                <AccordionItem value="step-2" className="border-b-0 rounded-2xl border border-border/60 bg-background/50 px-4">
                  <AccordionTrigger className="hover:no-underline">
                    <span className="text-sm font-bold">مرحله ۲: سوال و جواب ({questions.length} سوال)</span>
                  </AccordionTrigger>
                  <AccordionContent className="pt-2">
                    <div className="rounded-xl border border-border/60 bg-background/80 p-4 max-h-[60vh] overflow-y-auto space-y-4">
                      {questions.length === 0 ? (
                        <p className="text-sm text-muted-foreground">سوالی استخراج نشده است.</p>
                      ) : (
                        questions.map((q, index) => (
                          <Card key={q.question_id} className="rounded-xl border-border/60">
                            <CardContent className="p-4 space-y-3">
                              <div className="flex items-start gap-3">
                                <span className="flex items-center justify-center w-7 h-7 rounded-full bg-primary/10 text-primary text-sm font-bold shrink-0">
                                  {index + 1}
                                </span>
                                <div className="flex-1 min-w-0">
                                  <MarkdownWithMath markdown={q.question_text_markdown} />
                                </div>
                              </div>

                              {q.options && q.options.length > 0 && (
                                <div className="space-y-2 pr-10">
                                  {q.options.map((opt) => (
                                    <div
                                      key={opt.label}
                                      className={`flex items-start gap-2 p-2 rounded-lg ${
                                        opt.label === q.correct_option_label
                                          ? 'bg-emerald-500/10 border border-emerald-500/20'
                                          : 'bg-muted/30'
                                      }`}
                                    >
                                      <span className="font-bold text-sm shrink-0">{opt.label})</span>
                                      <MarkdownWithMath markdown={opt.text_markdown} />
                                    </div>
                                  ))}
                                </div>
                              )}

                              {q.teacher_solution_markdown && (
                                <details className="pr-10">
                                  <summary className="text-sm text-primary cursor-pointer hover:underline">
                                    راه‌حل
                                  </summary>
                                  <div className="mt-2 p-3 bg-primary/5 rounded-lg">
                                    <MarkdownWithMath markdown={q.teacher_solution_markdown} />
                                  </div>
                                </details>
                              )}
                            </CardContent>
                          </Card>
                        ))
                      )}
                    </div>
                  </AccordionContent>
                </AccordionItem>
              </Accordion>
            </div>
          </Card>

          {/* Description */}
          {examPrep.description && (
            <Card className="rounded-2xl border-border/60">
              <CardHeader>
                <CardTitle className="text-base">توضیحات</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">{examPrep.description}</p>
              </CardContent>
            </Card>
          )}

          {/* Student Invite Section */}
          <StudentInviteSection
            isExpanded={isInviteExpanded}
            onToggle={() => setIsInviteExpanded((p) => !p)}
            sessionId={examPrep.id}
            pipelineType="exam_prep"
          />
          <ClassAnnouncementsCard sessionId={examPrep.id} sessionType="exam_prep" />
        </div>

        {/* Sidebar */}
        <div className="lg:col-span-1 space-y-4">
          {/* Stats Card */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">آمار کلی</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-primary/10 text-primary">
                    <FileQuestion className="h-4 w-4" />
                  </div>
                  <span className="text-sm text-muted-foreground">تعداد سوالات</span>
                </div>
                <span className="font-semibold">{questions.length}</span>
              </div>

              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-primary/10 text-primary">
                    <Users className="h-4 w-4" />
                  </div>
                  <span className="text-sm text-muted-foreground">دانش‌آموزان دعوت شده</span>
                </div>
                <span className="font-semibold">{invites.length}</span>
              </div>

              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-primary/10 text-primary">
                    <Calendar className="h-4 w-4" />
                  </div>
                  <span className="text-sm text-muted-foreground">تاریخ ایجاد</span>
                </div>
                <span className="font-semibold text-xs">
                  {formatPersianDate(examPrep.created_at)}
                </span>
              </div>

              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-primary/10 text-primary">
                    <Clock className="h-4 w-4" />
                  </div>
                  <span className="text-sm text-muted-foreground">آخرین بروزرسانی</span>
                </div>
                <span className="font-semibold text-xs">
                  {formatDistanceToNow(new Date(examPrep.updated_at), { addSuffix: true, locale: faIR })}
                </span>
              </div>
            </CardContent>
          </Card>

          {/* Publication Status */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <CheckCircle className="h-4 w-4" />
                وضعیت انتشار
              </CardTitle>
            </CardHeader>
            <CardContent>
              {examPrep.is_published ? (
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-emerald-600">
                    <CheckCircle className="h-4 w-4" />
                    <span className="text-sm font-medium">منتشر شده</span>
                  </div>
                  {examPrep.published_at && (
                    <p className="text-xs text-muted-foreground">
                      تاریخ انتشار: {formatPersianDateTime(examPrep.published_at)}
                    </p>
                  )}
                </div>
              ) : isProcessing ? (
                <div className="flex items-center gap-2 text-amber-600">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span className="text-sm">در حال پردازش...</span>
                </div>
              ) : canPublish ? (
                <div className="space-y-3">
                  <p className="text-sm text-muted-foreground">
                    آزمون آماده انتشار است. پس از انتشار، دانش‌آموزان می‌توانند به آن دسترسی داشته باشند.
                  </p>
                  <Button className="w-full" size="sm" onClick={handlePublish} disabled={isPublishing}>
                    {isPublishing && <Loader2 className="h-4 w-4 ml-2 animate-spin" />}
                    انتشار آزمون
                  </Button>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  {examPrep.status === 'failed'
                    ? 'خطایی در پردازش رخ داده است.'
                    : 'آزمون هنوز آماده انتشار نیست.'}
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
