import * as z from 'zod';

export const PASSWORD_GUIDANCE =
  'حداقل ۸ کاراکتر، شامل یک حرف بزرگ انگلیسی، یک حرف کوچک انگلیسی و یک عدد.';

export const PASSWORD_POLICY_ERROR =
  'رمز عبور باید ۸ تا ۱۲۸ کاراکتر و شامل حداقل یک حرف بزرگ انگلیسی، یک حرف کوچک انگلیسی و یک عدد باشد. فاصله و حروف فارسی مجاز نیست.';

export function getPasswordPolicyError(value: string): string | null {
  if (value.length < 8 || value.length > 128) return PASSWORD_POLICY_ERROR;
  if (!/^[\x21-\x7E]+$/.test(value)) return PASSWORD_POLICY_ERROR;
  if (!/[A-Z]/.test(value) || !/[a-z]/.test(value) || !/[0-9]/.test(value)) {
    return PASSWORD_POLICY_ERROR;
  }
  return null;
}

export const strongPasswordSchema = z.string().superRefine((value, ctx) => {
  const error = getPasswordPolicyError(value);
  if (error) ctx.addIssue({ code: z.ZodIssueCode.custom, message: error });
});
