'use client';

import { useMemo, useRef, useState, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import { useForm, Controller, type FieldErrors } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Loader2, ArrowLeft, ArrowRight, Check, UserRound, KeyRound, GraduationCap } from 'lucide-react';
import { toast } from 'sonner';

import {
  onboardingSchema,
  ONBOARDING_STEP_FIELDS,
  type OnboardingFormValues,
} from '@/lib/validations/onboarding';
import {
  completeOnboarding,
  getStoredUser,
  persistUser,
  normalizeApiError,
  type CompleteOnboardingPayload,
} from '@/services/auth-service';
import { landingFor } from '@/lib/auth-routing';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Progress } from '@/components/ui/progress';
import { PasswordInput } from '@/components/auth/password-input';
import {
  Card, CardContent, CardDescription, CardHeader, CardTitle,
} from '@/components/ui/card';
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '@/components/ui/select';

const STEP_META = [
  { title: 'ساخت حساب', desc: 'نام کاربری و رمزی بساز که از این پس با آن وارد می‌شوی.', icon: KeyRound },
  { title: 'اطلاعات تماس', desc: 'نام و شماره موبایلت را وارد کن.', icon: UserRound },
  { title: 'تکمیل پروفایل', desc: 'چند مورد کوتاه تا کارت راه بیفتد.', icon: GraduationCap },
];

const GRADES = [
  { value: '10', label: 'دهم' },
  { value: '11', label: 'یازدهم' },
  { value: '12', label: 'دوازدهم' },
];
const MAJORS = [
  { value: 'math', label: 'ریاضی فیزیک' },
  { value: 'science', label: 'علوم تجربی' },
  { value: 'humanities', label: 'علوم انسانی' },
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
  const advancingRef = useRef(false);
  const submittingRef = useRef(false);

  const me = useMemo(() => getStoredUser(), []);
  const role = (me?.role || 'student').toLowerCase();
  const isStudent = role === 'student';
  const isTeacher = role === 'teacher';

  const {
    register, handleSubmit, trigger, control, setError,
    formState: { errors },
  } = useForm<OnboardingFormValues>({
    resolver: zodResolver(onboardingSchema),
    mode: 'onTouched',
    defaultValues: {
      username: '', password: '', confirmPassword: '',
      email: me?.email || '',
      firstName: me?.first_name || '', lastName: me?.last_name || '',
      phone: me?.phone || '',
      grade: '', major: '', expertise: '',
    },
  });

  const goNext = async () => {
    if (advancingRef.current || submittingRef.current) return;
    advancingRef.current = true;
    setAdvancing(true);
    const currentStep = step;
    try {
      const ok = await trigger(ONBOARDING_STEP_FIELDS[currentStep]);
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
    if (isStudent) { payload.grade = values.grade || ''; payload.major = values.major || ''; }
    if (isTeacher) { payload.expertise = values.expertise || ''; }

    try {
      const updated = await completeOnboarding(payload);
      persistUser(updated);
      toast.success('حسابت کامل شد! خوش آمدی 🎉');
      router.replace(landingFor(updated.role));
    } catch (e) {
      const n = normalizeApiError(e);
      let jumped = false;
      Object.entries(n.fieldErrors).forEach(([key, msgs]) => {
        const field = FIELD_MAP[key] || (key as keyof OnboardingFormValues);
        setError(field, { message: msgs[0] });
        // Jump back to the step holding the first errored field.
        if (!jumped) {
          const idx = ONBOARDING_STEP_FIELDS.findIndex((f) => f.includes(field));
          if (idx >= 0) { setStep(idx); jumped = true; }
        }
      });
      toast.error(n.message || 'تکمیل اطلاعات ناموفق بود.');
      submittingRef.current = false;
      setSubmitting(false);
    }
  };

  const handleInvalidSubmit = (fieldErrors: FieldErrors<OnboardingFormValues>) => {
    const invalidStep = ONBOARDING_STEP_FIELDS.findIndex((fields) => (
      fields.some((field) => Boolean(fieldErrors[field]))
    ));
    if (invalidStep >= 0) setStep(invalidStep);
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
        <Progress value={((step + 1) / STEP_META.length) * 100} className="h-1.5" />
        <p className="text-[11px] text-muted-foreground">مرحله {step + 1} از {STEP_META.length}</p>
      </CardHeader>

      <CardContent>
        <form onSubmit={handleWizardSubmit} className="space-y-4" noValidate>
          {/* Step 1 — credentials */}
          {step === 0 && (
            <div className="space-y-4">
              <Field label="نام کاربری" error={errors.username?.message}>
                <Input dir="ltr" placeholder="username" autoComplete="username" {...register('username')} />
              </Field>
              <Field label="رمز عبور" error={errors.password?.message}>
                <PasswordInput placeholder="••••••••" autoComplete="new-password" {...register('password')} />
              </Field>
              <Field label="تکرار رمز عبور" error={errors.confirmPassword?.message}>
                <PasswordInput placeholder="••••••••" autoComplete="new-password" {...register('confirmPassword')} />
              </Field>
              <Field label="ایمیل" error={errors.email?.message}>
                <Input dir="ltr" type="email" placeholder="you@example.com" {...register('email')} />
              </Field>
            </div>
          )}

          {/* Step 2 — identity / contact */}
          {step === 1 && (
            <div className="space-y-4">
              <Field label="نام" error={errors.firstName?.message}>
                <Input placeholder="نام" {...register('firstName')} />
              </Field>
              <Field label="نام خانوادگی (اختیاری)" error={errors.lastName?.message}>
                <Input placeholder="نام خانوادگی" {...register('lastName')} />
              </Field>
              <Field label="شماره موبایل" error={errors.phone?.message}>
                <Input
                  dir="ltr" inputMode="numeric" placeholder="09xxxxxxxxx"
                  readOnly={isStudent}
                  className={isStudent ? 'bg-muted/50 cursor-not-allowed' : undefined}
                  {...register('phone')}
                />
                {isStudent && (
                  <p className="text-[11px] text-muted-foreground mt-1">
                    این شماره همان شماره‌ای است که با آن وارد شدی و قابل تغییر نیست.
                  </p>
                )}
              </Field>
            </div>
          )}

          {/* Step 3 — light role profile */}
          {step === 2 && (
            <div className="space-y-4">
              {isStudent && (
                <>
                  <Field label="پایه تحصیلی (اختیاری)" error={errors.grade?.message}>
                    <SelectField control={control} name="grade" placeholder="انتخاب پایه" options={GRADES} />
                  </Field>
                  <Field label="رشته (اختیاری)" error={errors.major?.message}>
                    <SelectField control={control} name="major" placeholder="انتخاب رشته" options={MAJORS} />
                  </Field>
                </>
              )}
              {isTeacher && (
                <Field label="تخصص / حوزهٔ تدریس (اختیاری)" error={errors.expertise?.message}>
                  <Input placeholder="مثلاً ریاضیات، فیزیک…" {...register('expertise')} />
                </Field>
              )}
              {!isStudent && !isTeacher && (
                <p className="text-sm text-muted-foreground py-4 text-center">
                  اطلاعات لازم کامل است. روی «پایان» بزن تا وارد پنل شوی.
                </p>
              )}
            </div>
          )}

          {/* Nav */}
          <div className="flex items-center justify-between gap-3 pt-2">
            {step > 0 ? (
              <Button type="button" variant="ghost" onClick={() => setStep((s) => s - 1)} disabled={advancing || submitting}>
                <ArrowRight className="ms-1 h-4 w-4" /> قبلی
              </Button>
            ) : <span />}

            {step < STEP_META.length - 1 ? (
              <Button type="button" onClick={goNext} disabled={advancing}>
                {advancing
                  ? <><Loader2 className="ms-1 h-4 w-4 animate-spin" /> در حال بررسی…</>
                  : <>بعدی <ArrowLeft className="me-1 h-4 w-4" /></>}
              </Button>
            ) : (
              <Button type="submit" disabled={submitting}>
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

function Field({ label, error, children }: { label: string; error?: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <Label className="text-sm font-bold">{label}</Label>
      {children}
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}

function SelectField({
  control, name, placeholder, options,
}: {
  control: ReturnType<typeof useForm<OnboardingFormValues>>['control'];
  name: 'grade' | 'major';
  placeholder: string;
  options: { value: string; label: string }[];
}) {
  return (
    <Controller
      control={control}
      name={name}
      render={({ field }) => (
        <Select value={field.value || ''} onValueChange={field.onChange} dir="rtl">
          <SelectTrigger><SelectValue placeholder={placeholder} /></SelectTrigger>
          <SelectContent>
            {options.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}
          </SelectContent>
        </Select>
      )}
    />
  );
}
