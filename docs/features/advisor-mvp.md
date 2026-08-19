# نقش مشاور (ADVISOR) — طرح MVP

وضعیت: **پیش‌نویس تأییدشده برای اجرا** · دامنه: MVP · نویسنده: تیم AI-Amooz
اپ جدید: `backend/apps/advisory/` · مسیر فرانت: `frontend/src/app/(advisor)/`

این سند تنها منبع حقیقت برای MVP نقش مشاور است. کد و این سند با هم لند می‌شوند.

---

## ۱. قفل دامنه (تصمیم‌های محصولی — تغییرناپذیر در MVP)

| موضوع | تصمیم |
|---|---|
| نقش‌ها | **فقط `ADVISOR`**. پشتیبان و مشاور ارشد و والدین: خارج از دامنه. |
| حالت کار | هم فریلنسر هم سازمانی، با **داشبورد سوییچ‌شو** (مکانیزم موجود `WorkspaceSwitcher`). |
| جذب دانش‌آموز (فریلنسر) | مشاور با **شماره تلفن** دانش‌آموزِ *موجود* دعوت می‌فرستد. **هرگز کاربر نمی‌سازد.** |
| جذب دانش‌آموز (سازمانی) | سازمان یک `StudyGroup` را **گروهی** به مشاور می‌سپارد. |
| دامنه تحصیلی | **تمام سطوح**. هیچ‌جا «کنکور» یا پایه‌ی سخت‌کدشده نداریم. |
| مدل زمانی | **هفته‌ای، تکرارشونده، لنگرزده به شنبه**. ماه = تجمیع هفته‌ها روی خواندن. |
| آزمون بیرونی / OCR | **خارج از MVP**. (فاز بعد، روی زیرساخت exam-prep موجود.) |
| LLM | **صفر تماس LLM و صفر تسک Celery در MVP.** |
| متریک | **یک متریک: تعهد = مجموع دقیقه‌های واقعی ÷ مجموع دقیقه‌های برنامه‌ریزی‌شده.** محاسبه روی خواندن، بدون ستون ذخیره‌شده. |
| Jalali سمت سرور | **اضافه نمی‌کنیم.** `jdatetime` در `requirements.txt` نیست و نباید بیاید. سیم روی Gregorian؛ شنبه‌محوری حساب محض است: `week_start = d - timedelta(days=(d.weekday() + 2) % 7)`. تبدیل جلالی فقط فرانت (`date-fns-jalali` + `lib/calendar.ts`). |
| Feature flag | **مکانیزمی نمی‌سازیم — خودِ نقش، فلگ است.** حساب ADVISOR فقط دستی توسط ادمین پلتفرم ساخته می‌شود (رانبوک: §۸.۱)؛ سمت دانش‌آموز، *وجود engagement فعال* فلگ است. |

### قانون سخت وابستگی
`advisory` مجاز است از `accounts` / `organizations` / `classes` import کند.
**`classes` هرگز نباید از `advisory` import کند.** یک تست بدون‌توکن این جهت را قفل می‌کند.

---

## ۲. مدل داده (۷ جدول — کل MVP)

```
Subject
  name(fa) · slug · is_active · organization FK(null=global) · created_at
  UniqueConstraint(name, organization)
  UniqueConstraint(name) WHERE organization IS NULL      ← لازم است: PG هر NULL را متمایز می‌بیند

AdvisoryEngagement                          ← حاملِ tenancy برای همه‌چیز
  advisor  FK User  on_delete=PROTECT       (limit_choices_to role=ADVISOR)
  student  FK User  on_delete=CASCADE
  mode     'freelance' | 'org'
  organization FK Organization null on_delete=CASCADE
  status   PENDING | ACTIVE | REJECTED | ENDED
  invited_at · invite_expires_at · started_on(date) · ended_at · terms_accepted_at
  CheckConstraint  (mode='freelance' AND organization IS NULL)
                OR (mode='org'       AND organization IS NOT NULL)
  UniqueConstraint(student)          WHERE status='ACTIVE'    ← یک مشاور فعال برای هر دانش‌آموز
  UniqueConstraint(advisor,student)  WHERE status='PENDING'   ← ضد‌اسپم دعوت
  Index(advisor,status) · Index(student,status) · Index(status,invite_expires_at)

StudentSubject
  engagement FK CASCADE · subject FK PROTECT · is_active
  UniqueConstraint(engagement, subject)

WeeklyPlan
  engagement FK CASCADE · week_start(date, شنبه) · status DRAFT|PUBLISHED · note · created_by FK User SET_NULL
  UniqueConstraint(engagement, week_start) · Index(engagement, -week_start)

WeeklyPlanItem
  plan FK CASCADE · student_subject FK PROTECT · day_offset 0..6 (0=شنبه) · planned_minutes · title
  Check 0<=day_offset<=6 · Check 0<planned_minutes<=960

DailyLog
  engagement FK CASCADE · log_date(date) · mood 1..5 null · note
  UniqueConstraint(engagement, log_date) · Index(engagement, -log_date)

DailyLogItem
  log FK CASCADE · student_subject FK PROTECT · actual_minutes
  UniqueConstraint(log, student_subject)
```

### چرا این شکل — سه تصمیم قفل‌شده
1. **`DailyLog` به `engagement` وصل است، نه به `User`.** هر ردیف داده‌ی دانش‌آموز، مالک و سازمانش را همراه خود دارد → کوئری tenancy همیشه یک join است، هرگز «کاربر جاری» نیست.
2. **کلید اتصال، `StudentSubject` است نه `Subject`** — هم در `WeeklyPlanItem` هم در `DailyLogItem`. اگر این را در گام ۴ تصمیم نگیریم، متریک تعهد در گام ۸ به مایگریشن نیاز پیدا می‌کند.
3. **`Subject` هرگز حذف نمی‌شود** (`PROTECT` + `is_active=False`). تاریخ برنامه‌ها نباید بمیرد.

### `on_delete` — هر مورد با دلیل
| رابطه | تصمیم | دلیل |
|---|---|---|
| advisor → engagement | `PROTECT` | حذف مشاور باید اول به END کردن روابط مجبور شود؛ داده‌ی یتیم ممنوع. |
| student → engagement | `CASCADE` | حذف شخص = حذف داده‌ی شخص. |
| organization → engagement | `CASCADE` | سازمان‌ها **hard delete** می‌شوند (`organizations/views.py:250`). `SET_NULL` باعث نقض CheckConstraint می‌شد. |
| subject → student_subject | `PROTECT` | تاریخ. |
| engagement → همه‌ی فرزندان | `CASCADE` | engagement ریشه‌ی مالکیت است. |

---

## ۳. یک مکانیزم برای tenancy — `advisory/services/scope.py`

مخزن، گیتِ سازمانی را به‌صورت یک `staticmethod` دستی در ~۱۹ نقطه صدا می‌زند (`IsOrgAdmin.check`). آن الگو را **تکرار نمی‌کنیم**.

```python
# apps/advisory/services/scope.py — تنها دری که به مدل‌های advisory باز می‌شود
def visible_engagements(user) -> QuerySet
def visible_logs(user)        -> QuerySet
def visible_plans(user)       -> QuerySet
```
هر view فقط از این‌ها می‌خواند. **تست نگهبان بدون‌توکن:** هیچ فایلی جز `scope.py` (و `admin.py`/مایگریشن‌ها) نباید مدل‌های advisory را مستقیم import کند.

---

## ۴. دفتر تصمیم — برای هر گپ، یک تصمیم

### الف) نقش و احراز هویت
| # | گپ | تصمیم |
|---|---|---|
| A1 | `role` فقط `max_length=10` است | `'ADVISOR'` = ۷ کاراکتر → جا می‌شود. افزودن مقدار به `TextChoices` فقط یک `AlterField` انتخاب‌ها می‌سازد (پیشینه: `accounts/migrations/0004`). expand-then-contract لازم نیست. |
| A2 | `landingFor()` هر نقش ناشناس را به `/home` می‌فرستد | مشاور بی‌صدا در ناحیه‌ی دانش‌آموز حبس می‌شد و همه‌ی لیست‌ها ۴۰۳ می‌دادند — **بدترین حالت شکست، چون شبیه کار کردن است.** `case 'advisor': return '/advisor'` + رفع pin در `(dashboard)/layout.tsx` + تست `lib/auth-routing.test.ts`. |
| A3 | **[لندماین]** `accounts/signals.py:10` هر کاربر تازه با `is_staff=True` را به زور `role=ADMIN` می‌کند | حساب مشاور **هرگز نباید تیک staff بخورد**. ✅ تست رگرسیون در `test_advisor_role.py`. **اصلاح گام ۱:** این force-flip فقط `if created:` است، پس تیک‌زدنِ staff روی مشاورِ *موجود* نقش را عوض نمی‌کند — ولی `IsPlatformAdmin` خودِ `is_staff` را می‌پذیرد، یعنی مشاور بی‌صدا دسترسی ادمین پلتفرم می‌گیرد در حالی که هنوز «مشاور» نمایش داده می‌شود. تصمیم: **هشدار در UI، نه بلاک** (ادمین ممکن است عمداً حساب پشتیبانی بسازد) — `(admin)/admin/users/page.tsx`. |
| A4 | **[لندماین جدید]** ADVISOR از انتهای زنجیره‌ی پروفایل می‌افتد (`signals.py:14-22`, `serializers.py:222-251`) → `PUT /api/accounts/profile/` برای مشاور **۲۰۰ می‌دهد ولی چیزی ذخیره نمی‌کند** | در MVP **مدل پروفایل نداریم** (عیناً مثل MANAGER، با کامنت صریح). فرانت در صفحه‌ی مشاور فیلدهای bio/location/expertise را **نشان نمی‌دهد**. اگر بعداً لازم شد: `AdvisorProfile` در مایگریشن جدا. |
| A5 | `IsStudentUser` علاوه بر دانش‌آموز **معلم را هم می‌پذیرد** | **بازش نمی‌کنیم.** برای اندپوینت‌های دانش‌آموزیِ advisory یک `IsStudentRole` سخت‌گیر جدید (فقط STUDENT). |
| A6 | آیا نقش پنجم مجوزی را بی‌صدا باز می‌کند؟ | **نه.** ممیزی شد: `IsPlatformAdmin` = `ADMIN or is_superuser or is_staff`؛ `IsTeacherUser` = `== TEACHER`؛ `IsStudentUser` = `in (STUDENT, TEACHER)`. هیچ الگوی `role != 'STUDENT'` در مخزن نیست. مشاور به‌صورت پیش‌فرض **هیچ چیز** نمی‌گیرد. ریسک واقعی برعکس است: `commons/views.py:1782` یک مشاور را در صورت انتصاب مدیر سازمان بی‌صدا به MANAGER تبدیل می‌کند → در آن نقطه ADVISOR هم باید محافظت شود. |
| A7 | ادمین چطور نقش را می‌دهد؟ | مجانی: `UserUpdateSerializer.role` از `User.Role.choices` می‌آید، پس ADVISOR خودکار در دراپ‌دان ادمین ظاهر می‌شود. فقط برچسب فارسی و `ROLE_MAP` فرانت. |

### ب) جذب دانش‌آموز (فریلنسر) — بحرانی‌ترین سطح
| # | گپ | تصمیم |
|---|---|---|
| B1 | استفاده از کد دعوت پایدار پلتفرم (`invite_codes.py:22`) | **ممنوع.** آن کد یک **اعتبار ورود دائمیِ بی‌رمز** است (`authentication/views.py:318` کد+تلفن → JWT). advisory راز پذیرش **خودش** را دارد: کوتاه‌عمر، **هش‌شده در کش**، سقف تلاش، کول‌داون — عیناً الگوی `otp_service.py:26-27,78-89`. گیت «دعوتِ منتشرشده» هرگز شل نمی‌شود. |
| B2 | چهار خروجی متمایزِ دعوت = **اوراکل شمارش تلفن→هویت+نقش** | پاسخ **همیشه یکنواخت**: `202 {"status":"sent"}`. تمام انشعاب‌ها به تسک پس‌زمینه منتقل می‌شود تا **هم محتوا هم تأخیر** یکنواخت باشد. |
| B3 | اندپوینت SMS احرازشده، اسکوپ `user` = **۳۰۰/دقیقه** را ارث می‌برد | چهار لایه: اسکوپ جدید `advisory_invite` **۱۰/ساعت**؛ کول‌داون سراسری **۱ بار در ۲۴ ساعت برای هر شماره**؛ سقف مشاور **۳۰/روز و ۵۰ دعوت PENDING باز** → ۴۲۹؛ بریکر پلتفرم **۲۰۰۰/روز** → ۵۰۳. |
| B4 | ساخت کاربر با شماره (`accounts/services.py:43`) | **هرگز.** ایندکس یکتای جزئی `uniq_student_phone` شماره را هویت پلتفرمی می‌کند. جذب = **فقط lookup + claim**. اگر شماره وجود ندارد → همان `202` یکنواخت، هیچ حسابی ساخته نمی‌شود. |
| B5 | افشای PII در لیست PENDING | `PendingInviteSerializer` جداگانه با allowlist: شماره‌ی **ماسک‌شده**، بدون `studentId`، بدون آواتار. (پیشینه‌ی نشتی: `TeacherStudentSerializer` که `inviteCode` را لو می‌داد — تکرار نشود.) |
| B6 | سوءاستفاده در پذیرش/رد | `404` نه `403`؛ `select_for_update` + آپدیت شرطی با بررسی rowcount؛ `IntegrityError → 409`؛ `invite_expires_at = now+14d`؛ بازتأییدِ شماره؛ `REJECTED` **نهایی** + ۳۰ روز بلوک همان جفت. |

### ج) حالت سازمانی
| # | گپ | تصمیم |
|---|---|---|
| C1 | خروج/تعلیق عضو سازمان **hard delete** است و سیگنالی ندارد → engagement فعالِ کهنه | سه‌لایه: join زنده روی عضویت در `scope.py` + تابع `end_org_engagements_for()` در نقاط حذف + یک مصالحه‌گر شبانه (پیشینه: `tasks.py:2248`). |
| C2 | فن‌اوت گروهی روی دانش‌آموزی که **قبلاً** engagement فریلنسری فعال دارد | یکتایی `status='ACTIVE'` می‌شکست. **هر دانش‌آموز در try/IntegrityError خودش، بیرونِ یک atomic بزرگ**؛ خروجی قابل‌مشاهده = **گزارش رد‌شده‌ها**. فن‌اوت جزئی، موفقیت است نه شکست. |
| C3 | مشاور سازمانی بی‌رضایت به لاگ دانش‌آموز دسترسی می‌گیرد | چهار الزام: ثبت `terms_accepted_at`؛ بنر درون‌برنامه‌ای برای دانش‌آموز؛ `started_on = today` (**دید عطف‌به‌ماسبق ممنوع**)؛ END خودکار + مصالحه. |
| C4 | `OrgRole` مقدار مشاور ندارد | `OrgRole.ADVISOR` (`max_length=16` جا دارد). ✅ گام ۱. **نیمه‌ی `role_map` این تصمیم ملغی شد:** `InvitationCode.TargetRole` عمداً مقدار مشاور نمی‌گیرد، چون کد دعوت سازمان خودش یک اعتبار ورودِ بی‌رمز است (همان دلیل B1) — انتساب مشاور به سازمان کار گام ۹ است، نه کد دعوت. |
| C5 | `MyWorkspacesView` بر اساس `org_role` فیلتر نمی‌کند | **مزیت است**: عضویت مشاور بدون هیچ تغییری به‌عنوان workspace ظاهر می‌شود. |

### د) داده‌ی نوجوانان و نگه‌داری
| # | تصمیم |
|---|---|
| D1 | مجموعه‌ی خوانندگان **صریح و شمرده**: دانش‌آموز خودش، مشاور فعالش، ادمین پلتفرم، مدیر سازمان (فقط تجمیعی). **معلم هیچ چیز نمی‌گیرد.** |
| D2 | نگه‌داری **۷۳۰ روز** برای لاگ‌ها. |
| D3 | خروجی‌گرفتن/حذف **به‌درخواست دانش‌آموز**؛ **مشاور اجازه‌ی ویرایش لاگ نوشته‌ی دانش‌آموز را ندارد** (فقط خواندن + نظر). |
| D4 | `AdvisoryAccessLog` تنها موردی است که **بعداً قابل اضافه‌کردن نیست** (تاریخ گذشته را نمی‌توان ساخت) → از گام ۶، همان لحظه‌ای که خواندن روشن می‌شود، نوشته می‌شود. |

### ه) دیپلوی
| # | تصمیم |
|---|---|
| E1 | فقط **`Dockerfile` ریشه** مایگریت می‌زند (`:28`). `backend/Dockerfile:38` فقط gunicorn است. هر گام: **بک‌اند اول، فرانت بعد، همان روز.** |
| E2 | `next.config.ts:22-28` خطای TS را نادیده می‌گیرد → **شکستِ تایپ دیپلوی می‌شود.** قبل از هر پوش: `npm run typecheck` اجباری. |
| E3 | `/admin/` از rewrite فرانت رد نمی‌شود → وریفای گام‌های ادمین‌محور **روی هاست بک‌اند** انجام می‌شود. |
| E4 | `WORKSPACE_STORAGE_KEY` سراسری است (به کاربر مقید نیست) → **namespacing به ازای کاربر** + افزودن به `clearAuthStorage()`. |

---

## ۵. پلن ۱۰ گامی — پایان هر گام: دیپلوی + چک زنده

قاعده: هیچ گامی «فقط مایگریشن» نیست؛ هر گام دقیقاً **یک چیز قابل دیدن** به سایت اضافه می‌کند.

| گام | چه چیزی اضافه می‌شود | مایگریشن | چک زنده (کلیک) | برگشت |
|---|---|---|---|---|
| **۱** | نقش وجود دارد و **قابل رسیدن** است: `User.Role.ADVISOR` + `OrgRole.ADVISOR` + `_USERNAME_PREFIX` + `landingFor('advisor')` + رفع pin در `(dashboard)` + `ROLE_MAP` + هر دو دراپ‌دان ادمین + یونیون‌های TS + پوسته‌ی `/advisor` + `IsAdvisorUser` + `IsStudentRole` | choices ×۲ | در **پنل ادمینِ سایت** (`/admin/users`) نقش یک کاربر را ADVISOR کن (**بدون تیک staff**) → لاگین → روی `/advisor` می‌نشیند، نه `/home`. جزئیات: §۸.۱ | نقش را برگردان |
| **۲** | اپ `advisory` + `Subject` + `advisory/admin.py` (سطح نوشتنِ ادمین) + `GET /api/advisory/subjects/` + صفحه‌ی `/advisor/subjects` + تست جهت‌ import | ۱ جدول | در جنگو ادمین (**هاست بک‌اند**) دو درس بساز → در `/advisor/subjects` دیده شوند | جدول خالی، بی‌خطر |
| **۳** | `AdvisoryEngagement` + claim فقط با lookup تلفن + راز پذیرشِ هش‌شده + `GET /api/advisory/me/engagement/` + **بنر پذیرش دانش‌آموز** | ۱ جدول | مشاور شماره‌ی یک دانش‌آموز واقعی را می‌فرستد → دانش‌آموز بنر می‌بیند → «قبول» → هر دو طرف ACTIVE می‌بینند | حذف engagement |
| **۴** | `StudentSubject` + چک‌باکس انتخاب درس‌ها (**اینجا `student_subject` به‌عنوان کلید اتصال گام ۸ قفل می‌شود**) | ۱ جدول | مشاور ۳ درس برای دانش‌آموز تیک می‌زند → دانش‌آموز همان ۳ را می‌بیند | خالی‌کردن جدول |
| **۵** | `DailyLog` + `DailyLogItem` + صفحه‌ی دانش‌آموزی `/study-log` + ورودی شرطی در نویگیشن | ۲ جدول | دانش‌آموز برای امروز دقیقه ثبت می‌کند → رفرش → باقی می‌ماند | ورودی نویگیشن مخفی |
| **۶** | فید ۷روزه‌ی **فقط‌خواندنی** مشاور + `week_start_for()` + شروع نوشتن `AdvisoryAccessLog` | **صفر** | مشاور فید را می‌بیند و لاگ دیروز دانش‌آموز آنجاست | برگشت کد، بی‌خطر |
| **۷** | `WeeklyPlan` + `WeeklyPlanItem` + فرم نوشتن برنامه‌ی هفتگی | ۲ جدول | مشاور برنامه‌ی شنبه‌تا‌جمعه می‌نویسد و PUBLISH می‌کند → دانش‌آموز آن را می‌بیند | برگشت به DRAFT |
| **۸** | **تعهد = واقعی ÷ برنامه‌ریزی‌شده**، روی خواندن، در هر دو سمت | **صفر** | برنامه ۶۰۰ دقیقه، ثبت ۳۰۰ → «۵۰٪» در هر دو داشبورد | برگشت کد، بی‌خطر |
| **۹** | حالت سازمانی: `POST /api/advisory/org/<org>/study-groups/<group>/advisor/` با فن‌اوت تحمل‌پذیر + **گزارش رد‌شده‌ها** | صفر (فیلدها در گام ۳ آمده) | مدیر سازمان یک گروه را به مشاور می‌دهد → مشاور دانش‌آموزان را می‌بیند؛ گزارش می‌گوید کدام‌ها رد شدند و چرا | END گروهی |
| **۱۰** | سوییچر workspace برای مشاور + گسترش تاگل `is_freelancer` به `['TEACHER','ADVISOR']` + namespacing کلید localStorage | صفر | مشاور بین «فضای شخصی» و سازمان سوییچ می‌کند و لیست دانش‌آموزان عوض می‌شود | سوییچر با ≤۱ فضا خودش را پنهان می‌کند |

**چرا لاگ (۵) قبل از برنامه (۷):** ریسک‌محور. وابستگی سختِ `DailyLog` فقط `StudentSubject` و یک engagement فعال با مشاوری‌ست که واقعاً می‌خواند — نه `WeeklyPlan`. اگر پذیرش دانش‌آموز شکست بخورد، در گام ۵ می‌فهمیم نه گام ۹.

**گام‌های ۶ و ۸ صفر مایگریشن دارند** → دو چک‌پوینت کاملاً برگشت‌پذیر در میانه‌ی مسیر.

---

## ۶. تست‌های منفی اجباری (نمونه‌های کلیدی)

- مشاور A لاگ دانش‌آموزِ مشاور B را نمی‌بیند → **404**
- مشاور با engagement `ENDED` → **404** (نه ۴۰۳؛ افشای وجود ممنوع)
- معلم روی هر اندپوینت advisory → **۴۰۳**
- دانش‌آموز دعوتِ متعلق به دیگری را قبول کند → **404**
- دو پذیرش همزمان → یکی ۲۰۰، دیگری **409**
- دعوت به شماره‌ی ناموجود → **۲۰۲ یکنواخت**، هیچ کاربری ساخته نشود
- ۱۱ دعوت در یک ساعت → **۴۲۹**
- همان شماره دو بار در ۲۴ ساعت → **۲۰۲** ولی SMS دوم ارسال نشود
- `mode='org'` با `organization=None` → **IntegrityError**
- دو engagement `ACTIVE` برای یک دانش‌آموز → **IntegrityError**
- فن‌اوت گروهی روی دانش‌آموزی که engagement فریلنسری دارد → بقیه موفق + گزارش رد
- کاربر با `is_staff=True` ساخته شود → روی ADMIN می‌افتد نه ADVISOR (رگرسیون A3)
- مشاور تلاش کند لاگ نوشته‌ی دانش‌آموز را ویرایش کند → **۴۰۳**
- هیچ فایل advisory جز `scope.py` مدل‌ها را import نکند (نگهبان)
- `classes` از `advisory` import نکند (نگهبان)

---

## ۷. کارهای صریحاً خارج از MVP

OCR آزمون بیرونی · نقش والدین · پشتیبان/مشاور ارشد · هر تماس LLM · هر تسک Celery (جز مصالحه‌گر شبانه‌ی گام ۹) · `AdvisorProfile` · تجمیع ماهانه‌ی ذخیره‌شده · نوتیفیکیشن پیشرفته.

---

## ۸. ثبت اجرا — گام ۱ (نقش وجود دارد و قابل رسیدن است)

وضعیت: **کامل، تست‌شده، آماده‌ی دیپلوی.** صفر تماس شبکه، صفر توکن.

### ۸.۱ رانبوک ساخت حساب مشاور — **پلن اولیه اشتباه بود**

پلن فرض کرده بود مشاور در **جنگو ادمین** ساخته می‌شود. این **ناممکن است**:

- `apps/accounts/admin.py` **وجود ندارد** — `accounts.User` در جنگو ادمین **هیچ‌جا رجیستر نشده** (فقط `commons`/`organizations`/`waitlist` ادمین دارند).
- **اندپوینت ساخت کاربر نداریم**؛ `commons/urls.py` فقط `users/`, `users/stats/`, `users/<pk>/`, `users/<pk>/org-manager/…` را می‌دهد.
- ثبت‌نام عمومی **فقط STUDENT** است (`RegisterSerializer._VALID_ROLES = {User.Role.STUDENT}`).

**رانبوک واقعی (صفر کد جدید):**
1. مشاور مثل هر کاربر دیگری **خودش ثبت‌نام می‌کند** (نقش STUDENT).
2. ادمین پلتفرم در `/admin/users` نقش او را به «مشاور» تغییر می‌دهد →
   `PATCH /api/admin/users/<id>/ {"role": "ADVISOR"}`.
3. تیک **Staff را خاموش بگذارد** (هشدار زردِ همان دیالوگ).

این PATCH **تنها راه موجودیت یک حساب ADVISOR** است، پس با ۵ تست در
`apps/commons/test_admin_users.py::TestPromoteToAdvisor` قفل شد. اگر روزی این
PATCH مقدار `ADVISOR` را نپذیرد، کل فیچر در پروداکشن **غیرقابل‌دسترس** می‌شود
در حالی که همه‌ی تست‌های advisory سبز می‌مانند — دلیل وجود آن تست‌ها همین است.

### ۸.۲ آنچه لند شد

**بک‌اند** — `accounts/models.py` (مقدار enum + کامنت «هیچ مجوزی نمی‌دهد»)،
`accounts/migrations/0008_alter_user_role_advisor.py` (فقط choices)،
`accounts/services.py` (`_USERNAME_PREFIX['ADVISOR']='advisor'` — بدون آن
`prefix` به `'user'` سقوط می‌کرد)، `accounts/signals.py` (کامنت: MANAGER و
ADVISOR عمداً پروفایل ندارند)، `organizations/models.py` + `migrations/0011…`،
`core/permissions.py` (`IsAdvisorUser`, `IsStudentRole`)،
`commons/views.py` (گیت انتصاب مدیر سازمان).

**فرانت** — `lib/auth-routing.ts` + تست، `types/index.ts` (یونیون `role` و
`OrgRole`)، `(admin)/admin/users/page.tsx` (برچسب/آیکن/آمار/فیلتر/دراپ‌دان +
هشدار staff)، `(admin)/admin/llm-usage/page.tsx` (`ROLE_MAP`)،
`components/auth/login-form.tsx` (اصلاح `?next`)،
`(advisor)/advisor/{layout,page}.tsx`، کامنت در `(dashboard)/layout.tsx` و
`components/organization/org-management-panel.tsx`.

### ۸.۳ تصمیم‌های اصلاح‌شده یا جلو‌افتاده در گام ۱

| # | موضوع | تصمیم نهایی |
|---|---|---|
| ۱ | A5 / `IsStudentRole` | **جلو افتاد** به گام ۱ (اولین مصرف: گام ۳). کنار `IsAdvisorUser` نوشته شد تا زوجِ مجوزها یک‌جا و با تست منفی لند شوند. |
| ۲ | `(dashboard)/layout.tsx` | **هیچ تغییر رفتاری لازم نبود.** شرط موجود `if (!r \|\| r === 'student') return false;` است و مقصد را از `landingFor()` می‌گیرد؛ به‌محض شناختن `advisor` درست کار کرد. فقط کامنت اضافه شد تا کسی «رفع pin» را دوباره اختراع نکند. |
| ۳ | گیت `commons/views.py` | **۴۰۰ صریح فارسی**، نه حفظ بی‌صدای نقش. انتصاب مدیر سازمان روی یک ADVISOR رد می‌شود و ادمین مجبور می‌شود اول نقش را عوض کند (چون نقش، مسیر لندینگ را تعیین می‌کند). |
| ۴ | `?next` در فرم لاگین | باگ واقعی پیدا و رفع شد: مشاور با `?next` به شاخه‌ی دانش‌آموز می‌افتاد و دانش‌آموز `?next=/advisor` می‌گرفت. `PANEL_PREFIXES` هر پیشوند پنل را به یک نقش می‌بندد. |
| ۵ | `ROLE_OPTIONS` در `org-management-panel.tsx` | **عمداً ۴ گزینه ماند.** افزودن `'advisor'` آنجا فقط `org_role=advisor` + `role=STUDENT` می‌ساخت: بی‌اثر و در لیست اعضا از مشاور واقعی تفکیک‌ناپذیر. مالک این جریان گام ۹ است. |
| ۶ | تنزل ADVISOR → STUDENT | ارتقای STUDENT→ADVISOR شماره را از ایندکس `uniq_student_phone` آزاد می‌کند؛ اگر آن شماره بعداً گرفته شود، تنزل می‌تواند با IntegrityError ۵۰۰ بدهد. **از قبل موجود** است (عیناً برای TEACHER→STUDENT) → عمداً در گام ۱ رفع نشد. |

### ۸.۴ وریفای انجام‌شده

- `apps/accounts` + `apps/commons` + `apps/organizations` + `apps/core` + `apps/authentication` → **۴۴۳ passed**.
- `test_advisor_role.py` (۱۳ تست) + `TestPromoteToAdvisor` (۵ تست) سبز.
- `makemigrations --check --dry-run` → *No changes detected*.
- `npx tsc --noEmit` → exit 0 · `npx tsx --test src/lib/auth-routing.test.ts` → ۴/۴ · `next build` سبز با `○ /advisor` در جدول مسیرها.

> **نکته‌ی خارج از دامنه (ثبت شد تا گم نشود):** ۵۱ تست exam-prep در سوئیت کامل
> از قبل سرخ‌اند و به گام ۱ ربطی ندارند: (الف) `apps/classes/urls_v4.py` در
> **هیچ‌کجا include نشده** → همه‌ی مسیرهای `exam-prep-v4/…` ۴۰۴ می‌دهند؛
> (ب) یک تست v4 فرض می‌کند `AVALAI_API_KEY` خالی است و با کلید واقعیِ `.env`
> **کلید را در لاگ تست چاپ می‌کند** (نقض قانون «هیچ‌وقت کلید را چاپ نکن»)؛
> (ج) یک تست به‌خاطر محدودیت ۲۶۰ کاراکتری مسیر در ویندوز می‌شکند.

