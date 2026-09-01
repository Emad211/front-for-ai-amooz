'use client';

import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { Contact } from 'lucide-react';

import {
  AdvisoryService,
  type IntakePayload,
} from '@/services/advisory-service';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { IntakeProfileForm } from '@/components/advisory/intake-card';

const EMPTY_INTAKE: IntakePayload = {
  school: '',
  city: '',
  lastGpa: null,
  targetMajor: '',
  targetUniversity: '',
  mockExamInstitute: '',
  freeDayMinutes: null,
  classes: [],
};

/**
 * The student-side mirror of the intake profile («شناخت من», restart step 2):
 * the same shared form the advisor sees, wired to `/advisory/me/intake/`.
 *
 * Follows the quiet home-card rule of MySubjectsCard/StudyPlanCard: it renders
 * NOTHING at all until a successful read confirms an active advisor
 * (`active:false` arrives as a normal 200, and a failed fetch is swallowed) —
 * most students have no advisor and must not pay layout cost for this card.
 * A save without an advisor would answer 409 «ابتدا مشاور خود را تأیید
 * کنید.»; that Persian detail surfaces verbatim via toast.
 */
export function MyIntakeCard() {
  const [intake, setIntake] = useState<IntakePayload | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let active = true;
    AdvisoryService.getMyIntake()
      .then((resp) => {
        if (active && resp.active) setIntake(resp.intake ?? EMPTY_INTAKE);
      })
      .catch(() => {
        // Silent by design — see the component docstring.
      });
    return () => {
      active = false;
    };
  }, []);

  const handleSave = async (payload: IntakePayload) => {
    setSaving(true);
    try {
      await AdvisoryService.putMyIntake(payload);
      toast.success('فرم شناختت ذخیره شد.');
    } catch (err: unknown) {
      // Includes the no-advisor 409 copy, verbatim from the server.
      toast.error(err instanceof Error ? err.message : 'ذخیرهٔ فرم شناخت ناموفق بود.');
    } finally {
      setSaving(false);
    }
  };

  if (!intake) return null;

  return (
    <Card dir="rtl" className="rounded-2xl border-primary/20 bg-primary/5">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base font-semibold">
          <span className="rounded-lg bg-primary/10 p-1.5">
            <Contact className="h-4 w-4 text-primary" />
          </span>
          شناخت من
        </CardTitle>
        <p className="text-xs leading-relaxed text-muted-foreground">
          این اطلاعات به مشاورت کمک می‌کند برنامه‌ای متناسب با شرایطت
          بچیند؛ هر دو می‌توانید آن را ویرایش کنید.
        </p>
      </CardHeader>
      <CardContent>
        <IntakeProfileForm initial={intake} saving={saving} onSave={handleSave} />
      </CardContent>
    </Card>
  );
}
