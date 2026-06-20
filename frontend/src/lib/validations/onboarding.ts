import * as z from "zod";

/**
 * Forced post-login onboarding (3 steps). Every code-logged-in user sets the
 * username + password they'll use from now on, plus mandatory email + phone and
 * a few light, role-specific profile fields.
 */

const password = z
  .string()
  .min(8, { message: "رمز عبور باید حداقل ۸ کاراکتر باشد" })
  .max(128, { message: "رمز عبور نمی‌تواند بیشتر از ۱۲۸ کاراکتر باشد" })
  .refine((v) => !/^\d+$/.test(v), { message: "رمز عبور نمی‌تواند فقط عدد باشد" });

const phone = z
  .string()
  .min(6, { message: "شماره موبایل معتبر نیست" })
  .max(32, { message: "شماره موبایل معتبر نیست" })
  .transform((raw) => {
    const digits = String(raw ?? "").replace(/\D/g, "");
    if (digits.startsWith("98") && digits.length === 12) return `0${digits.slice(2)}`;
    if (digits.length === 10 && digits.startsWith("9")) return `0${digits}`;
    return digits;
  })
  .refine((d) => d.startsWith("09") && d.length === 11, { message: "شماره موبایل معتبر نیست" });

export const onboardingSchema = z
  .object({
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
    // Step 3 — light role profile (all optional)
    grade: z.string().optional().or(z.literal("")),
    major: z.string().optional().or(z.literal("")),
    expertise: z.string().trim().max(255).optional().or(z.literal("")),
  })
  .superRefine((data, ctx) => {
    if (data.confirmPassword && data.password !== data.confirmPassword) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "رمز عبور و تکرار آن یکسان نیست",
        path: ["confirmPassword"],
      });
    }
  });

export type OnboardingFormValues = z.infer<typeof onboardingSchema>;

/** Fields validated at each wizard step (for per-step `trigger`). */
export const ONBOARDING_STEP_FIELDS: (keyof OnboardingFormValues)[][] = [
  ["username", "password", "confirmPassword", "email"],
  ["firstName", "lastName", "phone"],
  ["grade", "major", "expertise"],
];
