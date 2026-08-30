'use client';

import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import { useForm, type FieldErrors } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Loader2, ArrowLeft, ArrowRight, Check, UserRound, KeyRound, GraduationCap } from 'lucide-react';
import { toast } from 'sonner';

import {
  createOnboardingSchema,
  ONBOARDING_STEP_FIELDS,
  type OnboardingFormValues,
} from '@/lib/validations/onboarding';
import { isMajorRequiredGrade } from '@/constants/grade-major';
import {
  completeOnboarding,
  getStoredUser,
  persistUser,
  normalizeApiError,
  type CompleteOnboardingPayload,
} from '@/services/auth-service';
import { landingFor } from '@/lib/auth-routing';

import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { OnboardingStepFields } from '@/components/auth/onboarding-step-fields';
import {
  Card, CardContent, CardDescription, CardHeader, CardTitle,
} from '@/components/ui/card';

const STEP_META = [
  { title: 'ساخت حساب', desc: 'نام کاربری و رمزی بساز که از این پس با آن وارد می‌شوی.', icon: KeyRound },
  { title: 'اطلاعات تماس', desc: 'نام و شماره موبایلت را وارد کن.', icon: UserRound },
  { title: 'تکمیل پروفایل', desc: 'چند مورد کوتاه تا کارت راه بیفتد.', icon: GraduationCap },
];

// Map backend snake_case field names → form field names for setError.
const FIELD_MAP: Record<string, keyof OnboardingFormValues> = {
  first_name: 'firstName',
  last_name: 'lastName',
};

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [advancing, setAdvancing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [focusField, setFocusField] = useState<keyof OnboardingFormValues | null>(null);
  const advancingRef = useRef(false);
  const submittingRef = useRef(false);

  const me = useMemo(() => getStoredUser(), []);
  const role = (me?.role || 'student').toLowerCase();
  const isStudent = role === 'student';
  const isTeacher = role === 'teacher';

  const {
    register, handleSubmit, trigger, control, setError, setFocus, watch, setValue,
    formState: { errors },
  } = useForm<OnboardingFormValues>({
    resolver: zodResolver(createOnboardingSchema(isStudent)),
    mode: 'onTouched',
    defaultValues: {
      username: '', password: '', confirmPassword: '',
      email: me?.email || '',
      firstName: me?.first_name || '', lastName: me?.last_name || '',
      phone: me?.phone || '',
      grade: '', major: '', expertise: '',
    },
  });

  useEffect(() => {
    if (!focusField) return;
    setFocus(focusField);
    setFocusField(null);
  }, [focusField, setFocus, step]);

  // Major applies only to grades '10'..'12'; hidden (and cleared) otherwise.
  const watchedGrade = watch('grade');
  const majorRequired = isMajorRequiredGrade(watchedGrade);
  useEffect(() => {
    if (!majorRequired) {
      setValue('major', '', { shouldValidate: false });
    }
  }, [majorRequired, setValue]);

  const goNext = async () => {
    if (advancingRef.current || submittingRef.current) return;
    advancingRef.current = true;
    setAdvancing(true);
    const currentStep = step;
    try {
      const ok = await trigger(ONBOARDING_STEP_FIELDS[currentStep], { shouldFocus: true });
      if (ok) {
        setStep((visibleStep) => (
          visibleStep === currentStep
            ? Math.min(visibleStep + 1, STEP_META.length - 1)
            : visibleStep
        ));
      }
    } finally {
      advancingRef.current = false;
      setAdvancing(false);
    }
  };

  const onSubmit = async (values: OnboardingFormValues) => {
    if (submittingRef.current) return;
    submittingRef.current = true;
    setSubmitting(true);
    const payload: CompleteOnboardingPayload = {
      username: values.username,
      password: values.password,
      email: values.email,
      phone: values.phone,
      first_name: values.firstName,
      last_name: values.lastName || '',
    };
    if (isStudent) {
      payload.grade = values.grade || '';
      // Major is sent only for grades '10'..'12'; omitted otherwise (≤09).
      if (isMajorRequiredGrade(values.grade)) payload.major = values.major || '';
    }
    if (isTeacher) { payload.expertise = values.expertise || ''; }

    try {
      const updated = await completeOnboarding(payload);
      persistUser(updated);
      toast.success('حسابت کامل شد! خوش آمدی 🎉');
      router.replace(landingFor(updated.role));
    } catch (e) {
      const n = normalizeApiError(e);
      let firstInvalidField: keyof OnboardingFormValues | null = null;
      Object.entries(n.fieldErrors).forEach(([key, msgs]) => {
        const field = FIELD_MAP[key] || (key as keyof OnboardingFormValues);
        setError(field, { message: msgs[0] });
        if (!firstInvalidField) {
          firstInvalidField = field;
          const idx = ONBOARDING_STEP_FIELDS.findIndex((f) => f.includes(field));
          if (idx >= 0) setStep(idx);
        }
      });
      if (firstInvalidField) setFocusField(firstInvalidField);
      toast.error(n.message || 'تکمیل اطلاعات ناموفق بود.');
      submittingRef.current = false;
      setSubmitting(false);
    }
  };

  const handleInvalidSubmit = (fieldErrors: FieldErrors<OnboardingFormValues>) => {
    const invalidStep = ONBOARDING_STEP_FIELDS.findIndex((fields) => (
      fields.some((field) => Boolean(fieldErrors[field]))
    ));
    if (invalidStep < 0) return;
    const invalidField = ONBOARDING_STEP_FIELDS[invalidStep].find((field) => Boolean(fieldErrors[field]));
    setStep(invalidStep);
    if (invalidField) setFocusField(invalidField);
  };

  const handleWizardSubmit = (event: FormEvent<HTMLFormElement>) => {
    if (step < STEP_META.length - 1) {
      event.preventDefault();
      void goNext();
      return;
    }
    if (submittingRef.current) {
      event.preventDefault();
      return;
    }
    void handleSubmit(onSubmit, handleInvalidSubmit)(event);
  };

  const Meta = STEP_META[step];
  const StepIcon = Meta.icon;

  return (
    <Card className="w-full max-w-md border-border/60 shadow-lg">
      <CardHeader className="space-y-3">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <StepIcon className="h-5 w-5" />
          </div>
          <div>
            <CardTitle className="text-lg font-black">{Meta.title}</CardTitle>
            <CardDescription className="text-xs">{Meta.desc}</CardDescription>
          </div>
        </div>
        <Progress
          value={((step + 1) / STEP_META.length) * 100}
          className="h-1.5"
          aria-label="پیشرفت تکمیل حساب"
        />
        <p className="text-[11px] text-muted-foreground">مرحله {step + 1} از {STEP_META.length}</p>
      </CardHeader>

      <CardContent>
        <form onSubmit={handleWizardSubmit} className="space-y-4" noValidate>
          <OnboardingStepFields
            step={step}
            isStudent={isStudent}
            isTeacher={isTeacher}
            currentPhone={me?.phone}
            register={register}
            control={control}
            errors={errors}
            grade={watchedGrade}
          />

          {/* Nav */}
          <div className="flex items-center justify-between gap-3 pt-2">
            {step > 0 ? (
              <Button type="button" variant="ghost" onClick={() => setStep((s) => s - 1)} disabled={advancing || submitting}>
                <ArrowRight className="ms-1 h-4 w-4" /> قبلی
              </Button>
            ) : <span />}

            {step < STEP_META.length - 1 ? (
              <Button key="next" type="button" onClick={(event) => { event.preventDefault(); void goNext(); }} disabled={advancing}>
                {advancing
                  ? <><Loader2 className="ms-1 h-4 w-4 animate-spin" /> در حال بررسی…</>
                  : <>بعدی <ArrowLeft className="me-1 h-4 w-4" /></>}
              </Button>
            ) : (
              <Button key="submit" type="submit" disabled={submitting}>
                {submitting
                  ? <><Loader2 className="ms-1 h-4 w-4 animate-spin" /> در حال ثبت…</>
                  : <><Check className="ms-1 h-4 w-4" /> پایان و ورود</>}
              </Button>
            )}
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
