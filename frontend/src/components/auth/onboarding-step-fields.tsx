'use client';

import { Controller } from 'react-hook-form';
import type { Control, FieldErrors, UseFormRegister } from 'react-hook-form';

import { GRADE_OPTIONS, MAJOR_OPTIONS, isMajorRequiredGrade } from '@/constants/grade-major';
import type { OnboardingFormValues } from '@/lib/validations/onboarding';
import { PasswordInput } from '@/components/auth/password-input';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

const fieldId = (name: keyof OnboardingFormValues) => `onboarding-${name}`;

type OnboardingStepFieldsProps = {
  readonly step: number;
  readonly isStudent: boolean;
  readonly isTeacher: boolean;
  readonly currentPhone?: string | null;
  readonly register: UseFormRegister<OnboardingFormValues>;
  readonly control: Control<OnboardingFormValues>;
  readonly errors: FieldErrors<OnboardingFormValues>;
  readonly grade?: string;
};

export function OnboardingStepFields({
  step,
  isStudent,
  isTeacher,
  currentPhone,
  register,
  control,
  errors,
  grade,
}: OnboardingStepFieldsProps) {
  if (step === 0) {
    return (
      <div className="space-y-4">
        <Field id={fieldId('username')} label="نام کاربری" error={errors.username?.message}>
          <Input id={fieldId('username')} dir="ltr" placeholder="username" autoComplete="username" aria-invalid={!!errors.username} aria-describedby={errors.username ? `${fieldId('username')}-error` : undefined} {...register('username')} />
        </Field>
        <Field id={fieldId('password')} label="رمز عبور" error={errors.password?.message}>
          <PasswordInput id={fieldId('password')} placeholder="••••••••" autoComplete="new-password" aria-invalid={!!errors.password} aria-describedby={errors.password ? `${fieldId('password')}-error` : undefined} {...register('password')} />
        </Field>
        <Field id={fieldId('confirmPassword')} label="تکرار رمز عبور" error={errors.confirmPassword?.message}>
          <PasswordInput id={fieldId('confirmPassword')} placeholder="••••••••" autoComplete="new-password" aria-invalid={!!errors.confirmPassword} aria-describedby={errors.confirmPassword ? `${fieldId('confirmPassword')}-error` : undefined} {...register('confirmPassword')} />
        </Field>
        <Field id={fieldId('email')} label="ایمیل" error={errors.email?.message}>
          <Input id={fieldId('email')} dir="ltr" type="email" placeholder="you@example.com" aria-invalid={!!errors.email} aria-describedby={errors.email ? `${fieldId('email')}-error` : undefined} {...register('email')} />
        </Field>
      </div>
    );
  }

  if (step === 1) {
    const phoneIsImmutable = isStudent && !!currentPhone;
    return (
      <div className="space-y-4">
        <Field id={fieldId('firstName')} label="نام" error={errors.firstName?.message}>
          <Input id={fieldId('firstName')} placeholder="نام" aria-invalid={!!errors.firstName} aria-describedby={errors.firstName ? `${fieldId('firstName')}-error` : undefined} {...register('firstName')} />
        </Field>
        <Field id={fieldId('lastName')} label="نام خانوادگی (اختیاری)" error={errors.lastName?.message}>
          <Input id={fieldId('lastName')} placeholder="نام خانوادگی" aria-invalid={!!errors.lastName} aria-describedby={errors.lastName ? `${fieldId('lastName')}-error` : undefined} {...register('lastName')} />
        </Field>
        <Field id={fieldId('phone')} label="شماره موبایل" error={errors.phone?.message}>
          <Input
            id={fieldId('phone')}
            dir="ltr"
            inputMode="numeric"
            placeholder="09xxxxxxxxx"
            readOnly={phoneIsImmutable}
            aria-invalid={!!errors.phone}
            aria-describedby={errors.phone ? `${fieldId('phone')}-error` : undefined}
            className={phoneIsImmutable ? 'bg-muted/50 cursor-not-allowed' : undefined}
            {...register('phone')}
          />
          {phoneIsImmutable && (
            <p className="mt-1 text-[11px] text-muted-foreground">
              این شماره همان شماره‌ای است که با آن وارد شدی و قابل تغییر نیست.
            </p>
          )}
        </Field>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {isStudent && (
        <>
          <Field id={fieldId('grade')} label="پایه تحصیلی" error={errors.grade?.message}>
            <SelectField control={control} name="grade" placeholder="انتخاب پایه" options={GRADE_OPTIONS} error={errors.grade?.message} />
          </Field>
          {isMajorRequiredGrade(grade) && (
            <Field id={fieldId('major')} label="رشته" error={errors.major?.message}>
              <SelectField control={control} name="major" placeholder="انتخاب رشته" options={MAJOR_OPTIONS} error={errors.major?.message} />
            </Field>
          )}
        </>
      )}
      {isTeacher && (
        <Field id={fieldId('expertise')} label="تخصص / حوزهٔ تدریس (اختیاری)" error={errors.expertise?.message}>
          <Input id={fieldId('expertise')} placeholder="مثلاً ریاضیات، فیزیک…" aria-invalid={!!errors.expertise} aria-describedby={errors.expertise ? `${fieldId('expertise')}-error` : undefined} {...register('expertise')} />
        </Field>
      )}
      {!isStudent && !isTeacher && (
        <p className="py-4 text-center text-sm text-muted-foreground">
          اطلاعات لازم کامل است. روی «پایان» بزن تا وارد پنل شوی.
        </p>
      )}
    </div>
  );
}

function Field({ id, label, error, children }: { readonly id: string; readonly label: string; readonly error?: string; readonly children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id} className="text-sm font-bold">{label}</Label>
      {children}
      {error && <p id={`${id}-error`} className="text-xs text-destructive">{error}</p>}
    </div>
  );
}

function SelectField({
  control,
  name,
  placeholder,
  options,
  error,
}: {
  readonly control: Control<OnboardingFormValues>;
  readonly name: 'grade' | 'major';
  readonly placeholder: string;
  readonly options: readonly { readonly value: string; readonly label: string }[];
  readonly error?: string;
}) {
  return (
    <Controller
      control={control}
      name={name}
      render={({ field }) => (
        <Select value={field.value || ''} onValueChange={field.onChange} dir="rtl">
          <SelectTrigger
            ref={field.ref}
            id={fieldId(name)}
            name={field.name}
            aria-invalid={!!error}
            aria-describedby={error ? `${fieldId(name)}-error` : undefined}
          >
            <SelectValue placeholder={placeholder} />
          </SelectTrigger>
          <SelectContent>
            {options.map((option) => (
              <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      )}
    />
  );
}
