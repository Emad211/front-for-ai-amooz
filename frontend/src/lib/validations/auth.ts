import * as z from "zod";

export const loginSchema = z.object({
  username: z.string().min(3, {
    message: "نام کاربری باید حداقل ۳ کاراکتر باشد",
  }).email({
    message: "لطفاً یک ایمیل معتبر وارد کنید",
  }).or(z.string().min(3, {
    message: "نام کاربری باید حداقل ۳ کاراکتر باشد",
  })),
  password: z.string().min(6, {
    message: "رمز عبور باید حداقل ۶ کاراکتر باشد",
  }),
});

export const joinCodeSchema = z.object({
  code: z.string().min(6, {
    message: "کد دعوت باید حداقل ۶ کاراکتر باشد",
  }).max(20, {
    message: "کد دعوت نمی‌تواند بیشتر از ۲۰ کاراکتر باشد",
  }),
});

export type LoginFormValues = z.infer<typeof loginSchema>;
export type JoinCodeFormValues = z.infer<typeof joinCodeSchema>;
