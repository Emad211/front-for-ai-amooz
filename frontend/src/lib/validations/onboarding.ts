import * as z from "zod";
import { isValidIranPhone, normalizeIranPhone } from '@/lib/iran-phone';
import { strongPasswordSchema } from './password';
import {
  GRADE_OPTIONS,
  MAJOR_OPTIONS,
  MAJOR_REQUIRED_MESSAGE,
  isMajorRequiredGrade,
} from '@/constants/grade-major';

/**
 * Forced post-login onboarding (3 steps). Every code-logged-in user sets the
 * username + password they'll use from now on, plus mandatory email + phone and
 * a few light, role-specific profile fields.
 */

const password = strongPasswordSchema;

const phone = z
  .string()
  .min(6, { message: "شماره موبایل معتبر نیست" })
  .max(20, { message: "شماره موبایل معتبر نیست" })
  .transform(normalizeIranPhone)
  .refine(isValidIranPhone, { message: "شماره موبایل معتبر نیست" });

const onboardingFieldsSchema = z.object({
    // Step 1 — credentials
    username: z
      .string()
      .trim()
      .min(3, { message: "نام کاربری باید حداقل ۳ کاراکتر باشد" })
      .max(150, { message: "نام کاربری بیش از حد طولانی است" }),
    password,
    confirmPassword: z.string().min(1, { message: "تکرار رمز عبور الزامی است" }),
    email: z.string().trim().email({ message: "لطفاً یک ایمیل معتبر وارد کنید" }),
    // Step 2 — identity / contact
    firstName: z.string().trim().min(1, { message: "نام الزامی است" }),
    lastName: z.string().trim().max(150).optional().or(z.literal("")),
    phone,
    // Step 3 — light role profile (all optional unless the grade demands a major)
    grade: z.enum(GRADE_OPTIONS.map((g) => g.value) as [string, ...string[]])
      .optional()
      .or(z.literal("")),
    major: z.enum(MAJOR_OPTIONS.map((m) => m.value) as [string, ...string[]])
      .optional()
      .or(z.literal("")),
    expertise: z.string().trim().max(255).optional().or(z.literal("")),
  });

export function createOnboardingSchema(isStudent: boolean) {
  return onboardingFieldsSchema.superRefine((data, ctx) => {
    if (data.confirmPassword && data.password !== data.confirmPassword) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "رمز عبور و تکرار آن یکسان نیست",
        path: ["confirmPassword"],
      });
    }
    // National-curriculum rule: grades '10'..'12' REQUIRE a major; for every
    // other grade the major must stay empty (hidden/cleared in the UI and
    // omitted from the payload).
    if (isStudent && !data.grade) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "پایه تحصیلی الزامی است.",
        path: ["grade"],
      });
    }
    if (isStudent && isMajorRequiredGrade(data.grade) && !data.major) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: MAJOR_REQUIRED_MESSAGE,
        path: ["major"],
      });
    }
    if (isStudent && !isMajorRequiredGrade(data.grade) && data.major) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "برای این پایه انتخاب رشته امکان‌پذیر نیست",
        path: ["major"],
      });
    }
  });
}

export type OnboardingFormValues = z.infer<typeof onboardingFieldsSchema>;

/** Fields validated at each wizard step (for per-step `trigger`). */
export const ONBOARDING_STEP_FIELDS: (keyof OnboardingFormValues)[][] = [
  ["username", "password", "confirmPassword", "email"],
  ["firstName", "lastName", "phone"],
  ["grade", "major", "expertise"],
];
