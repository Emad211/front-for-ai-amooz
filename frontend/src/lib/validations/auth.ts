import * as z from "zod";

/**
 * Helpers
 */
const emailSchema = z
  .string()
  .trim()
  .email({ message: "لطفاً یک ایمیل معتبر وارد کنید" });

const usernameOrEmailSchema = z
  .string()
  .trim()
  .min(3, { message: "نام کاربری باید حداقل ۳ کاراکتر باشد" })
  .superRefine((value, ctx) => {
    // اگر کاربر چیزی شبیه ایمیل زد، همان را سخت‌گیرانه ایمیل چک کنیم
    if (value.includes("@")) {
      const parsed = emailSchema.safeParse(value);
      if (!parsed.success) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: "لطفاً یک ایمیل معتبر وارد کنید",
        });
      }
    }
  });

const passwordSchema = z
  .string()
  .min(8, { message: "رمز عبور باید حداقل ۸ کاراکتر باشد" })
  .max(128, { message: "رمز عبور نمی‌تواند بیشتر از ۱۲۸ کاراکتر باشد" })
  .refine((v) => !/^\d+$/.test(v), {
    message: "رمز عبور نمی‌تواند فقط عدد باشد",
  });

const iranMobileSchema = z
  .string()
  .min(6, { message: "شماره تماس معتبر نیست" })
  .max(32, { message: "شماره تماس معتبر نیست" })
  .transform((raw) => {
    const digits = String(raw ?? "").replace(/\D/g, "");

    // +98xxxxxxxxxx  -> 0xxxxxxxxxx
    if (digits.startsWith("98") && digits.length === 12) return `0${digits.slice(2)}`;

    // 9xxxxxxxxx -> 09xxxxxxxxx
    if (digits.length === 10 && digits.startsWith("9")) return `0${digits}`;

    return digits;
  })
  .refine((digits) => digits.startsWith("09") && digits.length === 11, {
    message: "شماره تماس معتبر نیست",
  });

/**
 * Schemas
 */
export const loginSchema = z.object({
  username: usernameOrEmailSchema,
  password: z.string().min(1, { message: "رمز عبور الزامی است" }),
  // نکته: برای login، مینیمم ۸ را اجباری نکردم چون ممکن است
  // حساب‌های قدیمی‌تر یا داده‌های تستی داشته باشید.
  // اگر مطمئن هستی همه پسوردها ۸+ هستند، می‌تونی همینجا passwordSchema بذاری.
});

export const joinCodeSchema = z.object({
  code: z
    .string()
    .trim()
    .min(6, { message: "کد دعوت باید حداقل ۶ کاراکتر باشد" })
    .max(20, { message: "کد دعوت نمی‌تواند بیشتر از ۲۰ کاراکتر باشد" }),
  phone: iranMobileSchema,
});

export const teacherSignupSchema = z
  .object({
    firstName: z.string().trim().min(1, { message: "نام الزامی است" }),
    lastName: z.string().trim().min(1, { message: "نام خانوادگی الزامی است" }),
    email: emailSchema,
    phone: iranMobileSchema,
    password: passwordSchema,
    confirmPassword: z.string().min(1, { message: "تکرار رمز عبور الزامی است" }),
  })
  .superRefine((data, ctx) => {
    if (data.confirmPassword.length > 0 && data.password !== data.confirmPassword) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "رمز عبور و تکرار آن یکسان نیست",
        path: ["confirmPassword"],
      });
    }

    // (اختیاری) اگر می‌خوای کمی شبیه ولیدیتور Django (UserAttributeSimilarity) بشه:
    // جلوگیری از اینکه پسورد دقیقا همان ایمیل باشد
    if (data.password && data.email && data.password === data.email) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "رمز عبور نباید با ایمیل یکسان باشد",
        path: ["password"],
      });
    }
  });

// ── Waitlist (access request) schemas ───────────────────────────────────────

const optionalEmailSchema = z
  .string()
  .trim()
  .optional()
  .refine((v) => !v || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v), {
    message: "لطفاً یک ایمیل معتبر وارد کنید",
  });

const optionalIntStringSchema = z
  .string()
  .trim()
  .optional()
  .refine((v) => !v || /^\d+$/.test(v), { message: "یک عدد معتبر وارد کنید" });

const optionalUrlSchema = z
  .string()
  .trim()
  .optional()
  .refine((v) => !v || /^https?:\/\/.+/.test(v), {
    message: "آدرس باید با http یا https شروع شود",
  });

export const teacherAccessRequestSchema = z.object({
  fullName: z.string().trim().min(3, { message: "نام و نام خانوادگی را کامل وارد کنید" }),
  phone: iranMobileSchema,
  email: optionalEmailSchema,
  expertise: z.string().trim().max(255).optional(),
  note: z.string().trim().max(1000).optional(),
});

export const orgAccessRequestSchema = z.object({
  fullName: z.string().trim().min(3, { message: "نام رابط را کامل وارد کنید" }),
  orgName: z.string().trim().min(2, { message: "نام سازمان آموزشی الزامی است" }),
  phone: iranMobileSchema,
  email: optionalEmailSchema,
  city: z.string().trim().max(120).optional(),
  expectedStudents: optionalIntStringSchema,
  website: optionalUrlSchema,
  note: z.string().trim().max(1000).optional(),
});

export const completeRegistrationSchema = z
  .object({
    username: z
      .string()
      .trim()
      .min(3, { message: "نام کاربری باید حداقل ۳ کاراکتر باشد" })
      .max(150, { message: "نام کاربری بیش از حد طولانی است" }),
    password: passwordSchema,
    confirmPassword: z.string().min(1, { message: "تکرار رمز عبور الزامی است" }),
  })
  .superRefine((data, ctx) => {
    if (data.confirmPassword.length > 0 && data.password !== data.confirmPassword) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "رمز عبور و تکرار آن یکسان نیست",
        path: ["confirmPassword"],
      });
    }
  });

export const passwordResetRequestSchema = z.object({
  identifier: z.string().trim().min(1, { message: "نام کاربری یا ایمیل را وارد کنید" }),
});

export const passwordResetConfirmSchema = z
  .object({
    code: z.string().trim().regex(/^\d{5,6}$/, { message: "کد تأیید را درست وارد کنید" }),
    password: passwordSchema,
    confirmPassword: z.string().min(1, { message: "تکرار رمز عبور الزامی است" }),
  })
  .superRefine((data, ctx) => {
    if (data.confirmPassword.length > 0 && data.password !== data.confirmPassword) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "رمز عبور و تکرار آن یکسان نیست",
        path: ["confirmPassword"],
      });
    }
  });

/**
 * Types
 */
export type LoginFormValues = z.infer<typeof loginSchema>;
export type PasswordResetRequestFormValues = z.infer<typeof passwordResetRequestSchema>;
export type PasswordResetConfirmFormValues = z.infer<typeof passwordResetConfirmSchema>;
export type JoinCodeFormValues = z.infer<typeof joinCodeSchema>;
export type TeacherSignupFormValues = z.infer<typeof teacherSignupSchema>;
export type TeacherAccessRequestFormValues = z.infer<typeof teacherAccessRequestSchema>;
export type OrgAccessRequestFormValues = z.infer<typeof orgAccessRequestSchema>;
export type CompleteRegistrationFormValues = z.infer<typeof completeRegistrationSchema>;
