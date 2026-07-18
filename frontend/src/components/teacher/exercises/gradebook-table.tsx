'use client';

/**
 * Class gradebook for one exercise: submissions list + per-question override
 * (llm_score stays immutable; the effective score is recomputed server-side).
 * Design: docs/features/exercise-hub.md.
 */
import { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';
import { Loader2, RotateCcw } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { MarkdownWithMath } from '@/components/content/markdown-with-math';
import {
  type SubmissionListItem,
  type SubmissionDetail,
  type SubmissionStatus,
  type QuestionOverride,
  listSubmissions,
  getSubmission,
  overrideSubmission,
  allowRedo,
} from '@/services/exercises-service';

const SUB_STATUS_LABEL: Record<SubmissionStatus, string> = {
  draft: 'پیش‌نویس',
  submitted: 'در انتظار نمره‌دهی',
  grading: 'در حال نمره‌دهی',
  graded: 'نمره‌دهی‌شده',
  grading_failed: 'خطا در نمره‌دهی',
};

// Answer photos are stored as storage paths (e.g. exercises/answers/…) and
// served by the Django /media proxy — resolve against the backend origin
// (same convention as markdown-with-math's resolveImgSrc).
const API_BASE = (process.env.NEXT_PUBLIC_API_URL || '')
  .replace(/\/+$/, '')
  .replace(/\/api$/, '');

function answerImageUrl(path: string): string {
  const s = String(path).trim();
  if (/^(https?:)?\/\//i.test(s) || s.startsWith('data:')) return s;
  return `${API_BASE}/media/${s.replace(/^\/+/, '').replace(/^media\//, '')}`;
}

export function GradebookTable({ exerciseId }: { exerciseId: number }) {
  const [rows, setRows] = useState<SubmissionListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [openId, setOpenId] = useState<number | null>(null);

  const refresh = useCallback(async () => {
    try {
      setRows(await listSubmissions(exerciseId));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در بارگذاری کارنامه');
    } finally {
      setLoading(false);
    }
  }, [exerciseId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  if (loading) {
    return (
      <div className="flex justify-center py-6">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (rows.length === 0) {
    return <p className="py-6 text-center text-sm text-muted-foreground">هنوز پاسخی ارسال نشده است.</p>;
  }

  return (
    <div dir="rtl" className="overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="sticky right-0 bg-background">دانش‌آموز</TableHead>
            <TableHead>وضعیت</TableHead>
            <TableHead>نمره</TableHead>
            <TableHead>عملیات</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((r) => (
            <TableRow key={r.id}>
              <TableCell className="sticky right-0 bg-background font-medium">{r.studentName}</TableCell>
              <TableCell>
                <div className="flex items-center gap-1">
                  <Badge variant={r.status === 'graded' ? 'default' : 'secondary'}>
                    {SUB_STATUS_LABEL[r.status]}
                  </Badge>
                  {r.isLate && <Badge variant="outline">با تأخیر</Badge>}
                  {r.overridden && <Badge variant="outline">ویرایش معلم</Badge>}
                </div>
              </TableCell>
              <TableCell>
                {r.scorePoints != null ? `${r.scorePoints} از ${r.maxPoints}` : '—'}
              </TableCell>
              <TableCell>
                <Button size="sm" variant="outline" onClick={() => setOpenId(r.id)}>
                  مشاهده و نمره‌دهی
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      {openId != null && (
        <GradingDialog
          submissionId={openId}
          onClose={() => setOpenId(null)}
          onChanged={refresh}
        />
      )}
    </div>
  );
}

function GradingDialog({
  submissionId,
  onClose,
  onChanged,
}: {
  submissionId: number;
  onClose: () => void;
  onChanged: () => Promise<void>;
}) {
  const [detail, setDetail] = useState<SubmissionDetail | null>(null);
  const [overrides, setOverrides] = useState<Record<string, QuestionOverride>>({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    getSubmission(submissionId)
      .then(setDetail)
      .catch((err) =>
        toast.error(err instanceof Error ? err.message : 'خطا در بارگذاری پاسخ')
      );
  }, [submissionId]);

  const setOverride = (qid: string, patch: Partial<QuestionOverride>) => {
    setOverrides((prev) => ({ ...prev, [qid]: { ...prev[qid], ...patch, question_id: qid } }));
  };

  const save = async () => {
    const list = Object.values(overrides);
    if (list.length === 0) {
      onClose();
      return;
    }
    const invalidScore = (detail?.result.per_question ?? []).find((question) => {
      const score = overrides[question.question_id]?.teacher_score;
      const maxPoints = question.max_points;
      return score != null && (
        !Number.isFinite(score)
        || maxPoints == null
        || !Number.isFinite(maxPoints)
        || score < 0
        || score > maxPoints
      );
    });
    if (invalidScore) {
      toast.error(`نمره دستی باید بین صفر و ${invalidScore.max_points ?? 0} باشد.`);
      return;
    }
    setSaving(true);
    try {
      await overrideSubmission(submissionId, list);
      toast.success('نمره‌ها بازبینی شد.');
      await onChanged();
      onClose();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'ثبت نمره ناموفق بود.');
    } finally {
      setSaving(false);
    }
  };

  const redo = async () => {
    try {
      await allowRedo(submissionId);
      toast.success('به دانش‌آموز اجازهٔ ارسال مجدد داده شد.');
      await onChanged();
      onClose();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'عملیات ناموفق بود.');
    }
  };

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent dir="rtl" className="max-h-[85vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{detail?.studentName ?? 'پاسخ دانش‌آموز'}</DialogTitle>
        </DialogHeader>
        {!detail ? (
          <div className="flex justify-center py-8">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <div className="space-y-4">
            {(detail.result.per_question ?? []).map((pq) => {
              const qid = pq.question_id;
              const answer = detail.answers[qid];
              const teacherScore = Object.prototype.hasOwnProperty.call(
                overrides[qid] ?? {},
                'teacher_score'
              ) ? overrides[qid]?.teacher_score : pq.teacher_score;
              const scoreInvalid = teacherScore != null && (
                !Number.isFinite(teacherScore)
                || pq.max_points == null
                || teacherScore < 0
                || teacherScore > pq.max_points
              );
              return (
                <div key={qid} className="space-y-2 rounded-md border border-border p-3">
                  {answer?.text ? (
                    <div className="space-y-1 text-sm">
                      <p className="text-muted-foreground">پاسخ دانش‌آموز:</p>
                      <MarkdownWithMath markdown={answer.text} className="text-sm" />
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">
                      پاسخ دانش‌آموز: {answer?.images?.length ? '(پاسخ تصویری)' : '—'}
                    </p>
                  )}
                  {(answer?.images?.length ?? 0) > 0 && (
                    <div className="flex flex-wrap gap-2">
                      {(answer?.images ?? []).map((img) => (
                        <a
                          key={img}
                          href={answerImageUrl(img)}
                          target="_blank"
                          rel="noreferrer"
                          title="نمایش در اندازهٔ کامل"
                        >
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img
                            src={answerImageUrl(img)}
                            alt="پاسخ تصویری دانش‌آموز"
                            className="h-28 w-28 rounded-md border border-border object-cover"
                            loading="lazy"
                          />
                        </a>
                      ))}
                    </div>
                  )}
                  <p className="text-sm">
                    {/* Deterministic (MCQ/fill-blank) rows have no llm_score — before an
                        override, score_points still holds the automatic score. */}
                    نمرهٔ هوشمند:{' '}
                    {pq.llm_score ?? (pq.teacher_score == null ? pq.score_points ?? '—' : '—')} از{' '}
                    {pq.max_points ?? '—'}
                  </p>
                  {pq.feedback && (
                    <div className="rounded-md bg-muted p-2 text-sm">
                      <p className="mb-1 text-muted-foreground">بازخورد هوشمند:</p>
                      <MarkdownWithMath markdown={pq.feedback} />
                    </div>
                  )}
                  <div className="flex flex-wrap items-center gap-2">
                    <Label className="text-sm">نمرهٔ دستی</Label>
                    <Input
                      type="number"
                      min={0}
                      max={pq.max_points ?? undefined}
                      step="0.25"
                      className="w-24"
                      defaultValue={pq.teacher_score ?? undefined}
                      aria-invalid={scoreInvalid}
                      onChange={(e) => setOverride(qid, {
                        teacher_score: e.target.value === '' ? undefined : e.target.valueAsNumber,
                      })}
                    />
                    <Textarea
                      placeholder="بازخورد معلم (اختیاری)"
                      className="min-w-full"
                      rows={2}
                      onChange={(e) => setOverride(qid, { teacher_feedback: e.target.value })}
                    />
                    {scoreInvalid && (
                      <p className="min-w-full text-xs text-destructive">
                        نمره باید بین صفر و {pq.max_points ?? 0} باشد.
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
            <div className="flex items-center justify-between gap-2 border-t border-border pt-3">
              <Button variant="ghost" onClick={redo}>
                <RotateCcw className="ms-2 h-4 w-4" />
                اجازهٔ ارسال مجدد
              </Button>
              <Button onClick={save} disabled={saving}>
                {saving ? <Loader2 className="ms-2 h-4 w-4 animate-spin" /> : null}
                ثبت نمرهٔ دستی
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
