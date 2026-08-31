'use client';

import { useEffect, useState } from 'react';
import { Flag, Loader2, Pencil } from 'lucide-react';
import { toast } from 'sonner';

import {
  AdvisoryService,
  type GoalPayload,
} from '@/services/advisory-service';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';

const TARGET_MAX = 120;

export function GoalCard() {
  const [goal, setGoal] = useState<GoalPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [title, setTitle] = useState('');
  const [targetRank, setTargetRank] = useState('');
  const [currentRank, setCurrentRank] = useState('');
  const [note, setNote] = useState('');

  useEffect(() => {
    let active = true;
    AdvisoryService.getMyGoal()
      .then((res) => {
        if (!active || !res.active) return;
        setGoal(res.goal);
        if (res.goal) {
          setTitle(res.goal.targetTitle);
          setTargetRank(res.goal.targetRank);
          setCurrentRank(res.goal.currentRank);
          setNote(res.goal.note);
        } else {
          setEditing(true);
        }
      })
      .catch(() => {})
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const save = async () => {
    if (!title.trim()) {
      toast.error('متن هدف نمی‌تواند خالی باشد.');
      return;
    }
    setSaving(true);
    try {
      const saved = await AdvisoryService.saveMyGoal({
        targetTitle: title.trim(),
        targetRank,
        currentRank,
        note,
      });
      setGoal(saved);
      setEditing(false);
      toast.success('هدف ثبت شد');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'ثبت هدف ناموفق بود.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card dir="rtl" className="rounded-2xl border-primary/20 bg-primary/5">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center justify-between gap-2 text-base font-semibold">
          <span className="flex items-center gap-2">
            <span className="rounded-lg bg-primary/10 p-1.5">
              <Flag className="h-4 w-4 text-primary" />
            </span>
            هدف تحصیلی
          </span>
          {goal && !editing && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setEditing(true)}
              aria-label="ویرایش هدف"
            >
              <Pencil className="h-4 w-4" />
              ویرایش
            </Button>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {loading ? (
          <p className="text-sm text-muted-foreground">در حال بارگذاری…</p>
        ) : editing ? (
          <div className="space-y-2.5">
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value.slice(0, TARGET_MAX))}
              placeholder="مثلاً: پزشکی، دانشگاه شهید بهشتی"
              aria-label="هدف"
              className="bg-background"
            />
            <div className="grid grid-cols-2 gap-2">
              <Input
                value={targetRank}
                onChange={(e) => setTargetRank(e.target.value.slice(0, 60))}
                placeholder="رتبه/تراز هدف (اختیاری)"
                aria-label="رتبه هدف"
                className="bg-background text-xs"
              />
              <Input
                value={currentRank}
                onChange={(e) => setCurrentRank(e.target.value.slice(0, 60))}
                placeholder="رتبه/تراز فعلی (اختیاری)"
                aria-label="رتبه فعلی"
                className="bg-background text-xs"
              />
            </div>
            <Textarea
              value={note}
              onChange={(e) => setNote(e.target.value.slice(0, 500))}
              rows={2}
              placeholder="یادداشت مسیر… (اختیاری)"
              aria-label="یادداشت هدف"
              className="bg-background text-xs"
            />
            <div className="flex justify-end gap-2">
              {goal && (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => setEditing(false)}
                >
                  انصراف
                </Button>
              )}
              <Button type="button" size="sm" onClick={save} disabled={saving}>
                {saving && <Loader2 className="me-1 h-4 w-4 animate-spin" />}
                ذخیرهٔ هدف
              </Button>
            </div>
          </div>
        ) : goal ? (
          <div className="space-y-2">
            <p className="text-sm font-bold leading-relaxed">{goal.targetTitle}</p>
            {(goal.targetRank || goal.currentRank) && (
              <p className="flex flex-wrap gap-x-3 text-xs text-muted-foreground">
                {goal.currentRank && <span>فعلی: {goal.currentRank}</span>}
                {goal.targetRank && <span>هدف: {goal.targetRank}</span>}
              </p>
            )}
            {goal.note.trim() && (
              <p className="whitespace-pre-line text-xs leading-relaxed text-muted-foreground">
                {goal.note}
              </p>
            )}
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">
            فعلاً مشاور فعالی نداری؛ با پذیرش دعوت، هدف‌گذاری فعال می‌شود.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
