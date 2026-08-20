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
| دامنه تحصیلی | **تمام سطوح**. هیچ‌جا «کنکور» یا پایه‌ی سخت‌کدشده نداریم. (گام ۴ یک **برچسبِ پایه‌ی اختیاری** روی `Subject` افزود، صرفاً برای فیلترِ راحتیِ انتخابگر؛ درسِ بی‌برچسب = همه‌ی سطوح و همیشه نمایش داده می‌شود، پس این قفل نمی‌شکند — §۱۱.) |
| مدل زمانی | **هفته‌ای، تکرارشونده، لنگرزده به شنبه**. ماه = تجمیع هفته‌ها روی خواندن. |
| آزمون بیرونی / OCR | **خارج از MVP**. (فاز بعد، روی زیرساخت exam-prep موجود.) |
| LLM | **صفر تماس LLM در MVP.** تسک Celery فقط دو مورد: ارسال پیامک دعوت (صف `default`، گام ۳ — دلیل امنیتی: §۱۰.۲) و مصالحه‌گر شبانه‌ی گام ۹. |
| متریک | **یک متریک: تعهد = مجموع دقیقه‌های واقعی ÷ مجموع دقیقه‌های برنامه‌ریزی‌شده.** محاسبه روی خواندن، بدون ستون ذخیره‌شده. |
| Jalali سمت سرور | **اضافه نمی‌کنیم.** `jdatetime` در `requirements.txt` نیست و نباید بیاید. سیم روی Gregorian؛ شنبه‌محوری حساب محض است: `week_start = d - timedelta(days=(d.weekday() + 2) % 7)`. تبدیل جلالی فقط فرانت (`date-fns-jalali` + `lib/calendar.ts`). |
| Feature flag | **مکانیزمی نمی‌سازیم — خودِ نقش، فلگ است.** حساب ADVISOR فقط دستی توسط ادمین پلتفرم ساخته می‌شود (رانبوک: §۸.۱)؛ سمت دانش‌آموز، *وجود engagement فعال* فلگ است. |

### قانون سخت وابستگی
`advisory` مجاز است از `accounts` / `organizations` / `classes` import کند.
**`classes` هرگز نباید از `advisory` import کند.** یک تست بدون‌توکن این جهت را قفل می‌کند.

---

## ۲. مدل داده (۷ جدول — کل MVP)

```
Subject                                     ← لند شد در گام ۲ · grade در گام ۴ · انحراف‌ها: §۹.۲ · §۱۱
  name(fa) · normalized_name(مشتق از name، editable=False، db_index) · is_active
  grade(CharField(2)، '10'|'11'|'12'، null، db_index — برچسبِ فیلتر، نه هویت؛ NULL=همه‌ی سطوح)
  organization FK(null=global) · created_at · updated_at · created_by FK SET_NULL
  UniqueConstraint(normalized_name, organization)          ← grade عمداً در کلید یکتایی نیست
  UniqueConstraint(normalized_name) WHERE organization IS NULL   ← لازم است: PG هر NULL را متمایز می‌بیند

AdvisoryEngagement                          ← حاملِ tenancy · لند شد در گام ۳ · انحراف‌ها: §۱۰.۲
  advisor  FK User  on_delete=PROTECT       (limit_choices_to role=ADVISOR)
  student  FK User  on_delete=CASCADE
  mode     'freelance' | 'org'
  organization FK Organization null on_delete=CASCADE
  status   PENDING | ACTIVE | REJECTED | ENDED
  invited_phone(CharField، تلفن دعوت‌شده — افزوده در گام ۳ برای بازبینی سمت‌سرور هنگام پذیرش؛ §۱۰.۲)
  invited_at · invite_expires_at · started_on(date) · ended_at · terms_accepted_at
  CheckConstraint  (mode='freelance' AND organization IS NULL)
                OR (mode='org'       AND organization IS NOT NULL)
  UniqueConstraint(student)          WHERE status='ACTIVE'    ← یک مشاور فعال برای هر دانش‌آموز
  UniqueConstraint(advisor,student)  WHERE status='PENDING'   ← ضد‌اسپم دعوت
  Index(advisor,status) · Index(student,status) · Index(status,invite_expires_at)

StudentSubject                              ← لند شد در گام ۴ · §۱۱
  engagement FK CASCADE · subject FK PROTECT · is_active(set-replace با toggle، نه حذف ردیف)
  UniqueConstraint(engagement, subject) · Index(engagement, is_active)

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

OCR آزمون بیرونی · نقش والدین · پشتیبان/مشاور ارشد · هر تماس LLM · هر تسک Celery (جز ارسال پیامک دعوت در گام ۳ و مصالحه‌گر شبانه‌ی گام ۹) · `AdvisorProfile` · تجمیع ماهانه‌ی ذخیره‌شده · نوتیفیکیشن پیشرفته.

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
> از قبل سرخ بودند و به گام ۱ ربطی نداشتند: (الف) `apps/classes/urls_v4.py` در
> **هیچ‌کجا include نشده** → همه‌ی مسیرهای `exam-prep-v4/…` ۴۰۴ می‌دادند؛
> (ب) یک تست v4 فرض می‌کرد `AVALAI_API_KEY` خالی است و با کلید واقعیِ `.env`
> **کلید را در لاگ تست چاپ می‌کرد** (نقض قانون «هیچ‌وقت کلید را چاپ نکن»)؛
> (ج) یک تست به‌خاطر محدودیت ۲۶۰ کاراکتری مسیر در ویندوز می‌شکست.
>
> **بسته شد (۲۰۲۶-۰۸-۱۹، به دستور مالک):** ۳۶ فایل `test_exam_prep_v4_*.py` حذف
> شدند (الف و ب) و سقف مسیر ویندوز رفع شد (ج). سوئیت کامل بک‌اند حالا
> **۲۱۰۸ passed / ۰ failed / ۲ skipped** است — یعنی از این پس هر سرخی در سوئیت،
> رگرسیونِ کار advisory است و قابل اعتماد. ممیزی:
> [`docs/EXAM_PREP_V4_DECOMMISSION_AUDIT.md`](../EXAM_PREP_V4_DECOMMISSION_AUDIT.md).

---

## ۹. ثبت اجرا — گام ۲ (اپ `advisory` + فهرست درس‌ها)

وضعیت: **کامل، تست‌شده، آماده‌ی دیپلوی.** صفر تماس شبکه، صفر توکن، صفر Celery.

چک زنده (§۵ سطر ۲): در **جنگو ادمین روی هاست بک‌اند** (`/admin/advisory/subject/`
— نه دامنه‌ی فرانت؛ رِرایت فرانت `/admin/` را پروکسی نمی‌کند، E3) دو درس بساز:
یکی با `organization` خالی (سراسری) و یکی با سازمان مشاور → در `/advisor/subjects`
هر دو با برچسب درست دیده شوند. برگشت: جدول را خالی کن؛ بی‌خطر است.

### ۹.۱ آنچه لند شد

**بک‌اند** — اپ نو `apps/advisory/`: `models.py` (`Subject`)، `migrations/0001_initial.py`
(۱ جدول، هر دو constraint با پیام فارسی)، `admin.py` (`SubjectAdmin` + ستون
«دامنه» + مهرِ `created_by`)، `serializers.py` (camelCase، همه read-only)،
`views.py` (`SubjectListView`)، `urls.py`، `services/text.py`
(`normalize_subject_name`)، `services/scope.py` (`advisor_organization_ids`).
ثبت در `core/settings.py` و `core/urls.py` (`api/advisory/`).

**فرانت** — `services/advisory-service.ts` (لایه‌ی API + رفرش خودکار توکن روی ۴۰۱)،
`lib/persian-search.ts` (**ابزار مشترک نو**)، `app/(advisor)/advisor/subjects/page.tsx`،
نویگیشن در `(advisor)/advisor/layout.tsx`، ارتقای کارت «درس‌ها» در `advisor/page.tsx`.

**تست** — `test_subject_catalog.py` (۳۱)، `test_subjects_api.py` (۱۹)،
`test_import_boundaries.py` (۷)، `lib/persian-search.test.ts` (۹).

### ۹.۲ تصمیم‌های اصلاح‌شده یا جلو‌افتاده در گام ۲

| # | موضوع | تصمیم نهایی |
|---|---|---|
| ۱ | `slug` در شکل قفل‌شده‌ی §۲ | **حذف شد.** هیچ‌جا مصرف نداشت (نه URL، نه lookup) و برای نام فارسی یا `allow_unicode=True` می‌خواست یا به رشته‌ی خالی سقوط می‌کرد. §۲ به شکل واقعیِ لند‌شده اصلاح شد. |
| ۲ | کلید یکتایی | **از `name` به `normalized_name` منتقل شد** (فیلد مشتق، `editable=False`). بدون آن «ریاضي» و «ریاضی» دو ردیف مجاز بودند و مشاور دو گزینه‌ی یکسان می‌دید. constraint دوم (partial، `WHERE organization IS NULL`) عیناً حفظ شد — چون PG هر NULL را متمایز می‌بیند، آن یکی است که فهرست سراسری را واقعاً یکتا می‌کند. |
| ۳ | اعتبارسنجی تکراری در ادمین | **کوئری صریح در `Model.clean()`**، نه اتکا به `validate_constraints`. `editable=False` باعث می‌شود `_get_validation_exclusions()` فیلد را کنار بگذارد و اعتبارسنجی هر constraint متکی به آن **بی‌صدا رد شود** → ادمین با `IntegrityError` ۵۰۰ می‌داد. حالا خطای فیلدی فارسی روی `name` می‌نشیند و constraint‌های DB ضمانت سختِ پشتی‌اند. |
| ۴ | صفحه‌بندی اندپوینت | **`pagination_class = None`.** پیش‌فرض DRF سراسری است (`PAGE_SIZE` از `DRF_PAGE_SIZE`، پیش‌فرض ۵۰) و یک اندپوینتِ «انتخابگر» را بی‌صدا قطع می‌کرد. مرتب‌سازی هم صریح است: `F('organization_id').asc(nulls_first=True)` چون PG در ASC، NULL را آخر می‌گذارد. |
| ۵ | `services/scope.py` | **جلو افتاد** از گام ۶ به گام ۲. اولین مصرفش همین کوئری (سراسری ∪ سازمان‌های مشاور) بود؛ نوشتنش دو بار، یک بار موقت، تنها راهِ داشتن دو منطق tenancy بود. |
| ۶ | نگهبان import | باگ در **خودِ نگهبان** پیدا شد: هر import نسبی را به پیشوند ثابت `apps.advisory.` می‌بست → ۶۴ متخلفِ کاذب. با `_package_of()` رفع و با **دو تست که خود resolver را pin می‌کنند** قفل شد. نگهبانی که خودش تست ندارد، امنیتِ کاذب است. |
| ۷ | `lib/persian-search.ts` (فرانت) | **ابزار مشترک نو، عمداً جدا از کلید یکتایی بک‌اند.** جست‌وجوی فارسی بی‌فولد برای همان ورودی‌هایی می‌شکند که بک‌اند یک نرمال‌ساز کامل برایشان دارد (یای/کاف عربی، سه دستگاه رقم، ZWNJ) — و شکستش یعنی ردیفی که مشاور همین حالا می‌بیند با اولین حرفِ تایپ ناپدید شود، که «درس وجود ندارد» خوانده می‌شود نه «جست‌وجویم سخت‌گیر است». دو تابع دو **هدف متفاوت** دارند: کلید بک‌اند نباید هرگز دو درسِ واقعاً متفاوت را یکی کند، فولد فرانت باید سخاوتمند باشد. مصرف بعدی: گام‌های ۳، ۴، ۷. |
| ۸ | نویگیشن پنل مشاور | **در گام ۲ آمد، نه ۳/۷.** کامنت خودِ پوسته‌ی گام ۱ آن را مشروط به «بیش از یک مقصد» کرده بود و حالا دو مقصد هست. فعال‌بودن با **تطبیق دقیق** است نه `startsWith` — چون `/advisor` پیشوند هر مسیر خواهرش است و تب «خانه» همه‌جا روشن می‌ماند. |
| ۹ | حالت خطای صفحه | `subjects` روی شکست **`null` می‌ماند**، نه `[]`. آرایه‌ی خالی «فهرست خالی است» رندر می‌شود که ادعایی مادیْ متفاوت و گمراه‌کننده است؛ با `null`، دکمه‌ی «تلاش مجدد» در دسترس می‌ماند. |
| ۱۰ | `npm run lint` | **در کل ریپو خراب است** (`Converting circular structure to JSON … property 'react' closes the circle`، از `frontend/.eslintrc.json`). پیش‌از‌این وجود داشته: با اجرا روی یک فایل دست‌نخورده تأیید شد. **گیت واقعی فرانت `npm run typecheck` است** — چون `next.config.ts` هم `typescript.ignoreBuildErrors` و هم `eslint.ignoreDuringBuilds` را `true` گذاشته، خطای تایپ بی‌صدا دیپلوی می‌شود. |

### ۹.۳ وریفای انجام‌شده

- سوئیت **کامل** بک‌اند: **۲۱۶۵ passed / ۰ failed / ۲ skipped** (۴۴۰s).
  دقیقاً **۵۷+** نسبت به بیس‌لاین ۲۱۰۸ (§۸.۴) = همان ۵۷ تست advisory → **صفر رگرسیون**.
  دو skip، همان گاردهای از‌قبل‌موجودِ `test_pdf_accuracy_benchmark.py` است.
- `npx tsx --test src/lib/persian-search.test.ts` → **۹/۹**.
- `npm run typecheck` → پاک · `npm run build` → exit 0 با
  `/(advisor)/advisor/subjects/page` در `app-build-manifest.json`.
- `npm run lint` → **گیت نیست** (سطر ۱۰ بالا).

---

## ۱۰. ثبت اجرا — گام ۳ (`AdvisoryEngagement` + دعوت/پذیرش + بنر دانش‌آموز)

وضعیت: **کامل، تست‌شده، آماده‌ی دیپلوی.** صفر تماس LLM. یک تسک Celery روی صف
`default` (ارسال پیامک دعوت — دلیل امنیتی در §۱۰.۲/ردیف ۱).

چک زنده (§۵ سطر ۳): مشاور در `/advisor/students` **شماره‌ی یک دانش‌آموز واقعیِ
ثبت‌نام‌شده** را می‌فرستد → همان دانش‌آموز پس از ورود، **بنر دعوت** را بالای
داشبورد می‌بیند → «پذیرش» → هر دو طرف رابطه را ACTIVE می‌بینند (مشاور در فهرست
«همکاری‌های فعال»، دانش‌آموز با ناپدید‌شدن بنر). **برگشت:** ردیف `AdvisoryEngagement`
را از جنگو ادمین حذف کن؛ بی‌خطر است (هیچ جدول وابسته‌ای هنوز به آن اشاره نمی‌کند).

### ۱۰.۱ آنچه لند شد

**بک‌اند** — `models.py` (`AdvisoryEngagement` + `INVITE_TTL_DAYS=14` +
`REJECT_BLOCK_DAYS=30`)، `migrations/0002_advisoryengagement.py` (۱ جدول، ۱
check + ۲ unique جزئی + ۳ ایندکس، همه با پیام فارسی)، `services/invites.py`
(چهار سقفِ سهمیه + `deliver_invite` صرفاً lookup + `accept_invite`/`reject_invite`
با `select_for_update` و بازبینی تلفن)، `tasks.py` (تنها تسکِ MVP:
`deliver_advisory_invite_task`)، بسط `services/scope.py`
(`visible_engagements` / `advisor_students` / `advisor_pending_invites` /
`student_active_engagement` / `student_claimable_invites`)، `serializers.py`
(همه plain `Serializer`، تلفن همه‌جا ماسک، بدون `studentId`)، `views.py`
(روستر/اوت‌باکس + `AdvisoryInviteCreateView` با اسکوپِ `advisory_invite` +
پذیرش/رد سمت دانش‌آموز)، `urls.py`. اسکوپ throttle در `core/settings.py`.

**فرانت** — بسط `services/advisory-service.ts` (روستر/دعوت/پذیرش/رد + پیام‌های
خطای فیلدیِ DRF)، `app/(advisor)/advisor/students/page.tsx` (روستر + اوت‌باکس +
دعوت با شماره)، `components/advisory/advisor-invite-banner.tsx` (بنر پذیرشِ
دانش‌آموز)، نصب بنر در `(dashboard)/layout.tsx`، نویگیشن «دانش‌آموزان من» و ارتقای
کارت خانه‌ی مشاور.

**تست** — `test_engagement_model.py` (۲۸: constraintها، آبشار حذف، ماسک تلفن،
`is_expired`، اسکوپ، ضدنشتِ سریالایزر) و `test_engagement_invites.py` (۵۱: ماتریس
مجوز منفی، یکنواختیِ ۲۰۲، چهار سقف، عدم‌ساختِ کاربر، کول‌داون، مسابقه‌ی دو مشاور،
۴۰۴ به‌جای ۴۰۳، بلاکِ ۳۰‌روزه، پیامکِ بی‌کد).

### ۱۰.۲ تصمیم‌های اصلاح‌شده، انحراف‌ها و ریسک‌های دانسته در گام ۳

| # | موضوع | تصمیم نهایی |
|---|---|---|
| ۱ | **انحراف از §۱/§۷: یک تسک Celery.** | B2 می‌گوید چهار برایندِ دعوت (دانش‌آموز پیدا شد · شماره ناشناس · تلفن در کول‌داون · جفت بلاک‌شده) زمان‌های متفاوت می‌برند؛ انجامشان داخل ریکوئست، **زمان پاسخ** را به اوراکلِ شماره→هویت بدل می‌کند حتی اگر **بدنه** یکنواخت باشد. کل کار پشت یک `.delay()` رفت (صف `default`، مثل `send_publish_sms_task`) تا هزینه‌ی ریکوئست به‌طور ساختاری ثابت شود. §۱ و §۷ اصلاح شدند. |
| ۲ | **انحراف از §۲: فیلد `invited_phone`.** | §۲ فهرست فیلدها را قفل کرده بود و این یکی در آن نبود. لازم شد: هنگام «پذیرش»، تلفنِ *فعلیِ* مدعی با تلفنی که دعوت به آن رفته بازبینی می‌شود (B6)؛ اگر شماره بین دعوت و پذیرش دست‌به‌دست شده باشد، دعوت **مرده** است نه تحویلِ دیتای یک دانش‌آموز به انسانی دیگر. §۲ به شکل واقعی اصلاح شد. |
| ۳ | **بدون کُد پذیرش (B1).** | هیچ توکن/سکرت/کدی ساخته و ارسال نمی‌شود. پذیرش صرفاً با **سشن احرازشده‌ی دانش‌آموز + بازبینی سمت‌سرورِ تلفن** است. کدِ ثابتِ دعوتِ پلتفرم (اعتبارنامه‌ی ورودِ دائمی و بی‌رمز) هرگز بازاستفاده نشد. |
| ۴ | **اوراکلِ باقی‌مانده‌ی اوت‌باکس (ریسکِ دانسته، پذیرفته).** | وقتی مشاور شماره‌ی یک دانش‌آموزِ واقعی را می‌زند، ردیف PENDING در اوت‌باکسش ظاهر می‌شود؛ برای شماره‌ی ناشناس هیچ ردیفی. یعنی اوت‌باکس، «ثبت‌نام‌بودن یک شماره» را لو می‌دهد — **اما فقط برای شماره‌ای که خودِ مشاور تایپ کرده**، پس چیزی فراتر از دانسته‌ی خودش فاش نمی‌شود. کرانمند و آگاهانه پذیرفته شد (منطق B5). یکنواختیِ *پاسخِ دعوت* (بدنه + زمان) دست‌نخورده است. |
| ۵ | **قفلِ معماری: بدون `studentId` روی سیم.** | هیچ سریالایزری PKِ دانش‌آموز را بیرون نمی‌دهد؛ کلیدِ روستر، id خودِ engagement است و تلفن همه‌جا ماسک می‌شود. تستِ `test_the_roster_exposes_no_student_id` این را قفل می‌کند تا مصرف‌کننده‌ی آینده نتواند یک نگاشتِ id→دانش‌آموز بسازد. |
| ۶ | **جدولِ دعوتِ فقط‌تلفنی: به تعویق افتاد.** | مشاورِ فریلنسری که دانش‌آموزش هنوز ثبت‌نام نکرده، فعلاً **هیچ ردیفی نمی‌سازد** (اکتساب = lookup + claim، نه ساختِ کاربر). سناریوی «دعوتِ شماره‌ای که بعداً ثبت‌نام می‌کند» جزو MVP نیست؛ اگر لازم شد، جدولِ دعوتِ معلق روی تلفن، افزوده‌ای غیرشکننده روی همین مدل است. |
| ۷ | **۴۰۴ به‌جای ۴۰۳ در پذیرش/رد.** | دعوتِ متعلق به دیگری، منقضی، یا نهایی‌شده، **۴۰۴** می‌دهد نه ۴۰۳ — تا خودِ *وجودِ* یک دعوت برای مدعیِ اشتباه فاش نشود. `select_for_update` + نگاشتِ `IntegrityError→409` مسابقه‌ی دو مشاور برای یک دانش‌آموز را به «دقیقاً یک برنده» می‌رساند. |

### ۱۰.۳ وریفای انجام‌شده

- سوئیت اپ `advisory`: **۱۵۳ passed / ۰ failed** (۶٫۵s) — شاملِ ۷۹ تستِ نوِ گام ۳
  (۲۸ + ۵۱). دو skipِ بنچمارکِ exam-prep بیرون از این اسکوپ‌اند.
- `python manage.py makemigrations --check --dry-run` روی `advisory` → *No changes*.
- `npx tsc --noEmit` → پاک · `npm run build` → `✓ Compiled successfully in 8.4s`
  با هر سه مسیر به‌صورت استاتیک: `/advisor 4.42 kB` · `/advisor/students 8.31 kB`
  · `/advisor/subjects 7.35 kB`.
- `npm run lint` → همچنان **گیت نیست** (§۹.۲ ردیف ۱۰).

---

## ۱۱. ثبت اجرا — گام ۴ (انتخابِ درسِ دانش‌آموز · `StudentSubject`)

وضعیت: **کامل، تست‌شده، آماده‌ی دیپلوی.** صفر تماس LLM، صفر Celery — CRUDِ خالص.

چک زنده (§۵ سطر ۴): مشاور در `/advisor/students` روی «انتخاب درس‌ها»ی یک دانش‌آموزِ
ACTIVE می‌زند، ۳ درس را تیک می‌زند و «ذخیره» → همان دانش‌آموز در خانه‌ی داشبورد،
کارتِ «درس‌های مطالعاتی شما» را با همان ۳ درس می‌بیند. **برگشت:** ردیف‌های
`StudentSubject` را از جنگو ادمین غیرفعال/حذف کن؛ بی‌خطر است (فقط `WeeklyPlanItem`/
`DailyLogItem`ِ گام‌های بعد با PROTECT به آن اشاره می‌کنند و هنوز وجود ندارند).

### ۱۱.۱ آنچه لند شد

**بک‌اند** — `models.py` (`Subject.grade`ِ نال‌پذیر + `SUBJECT_GRADE_CHOICES`ِ محلی +
مدلِ `StudentSubject`)، `migrations/0003_subject_grade_studentsubject.py` (افزودنیِ
بی‌داون‌تایم: ستونِ نال‌پذیر بی‌بک‌فیل + ۱ جدول)، بسط `services/scope.py`
(`advisor_engagement` / `student_subjects` / `assignable_subjects`)، **درِ نوشتنِ نو**
`services/student_subjects.py` (`set_engagement_subjects` در ترنزاکشن + استثنای
`SubjectNotAssignable`)، `serializers.py` (`SubjectSerializer` + `grade`/`gradeLabel`،
`StudentSubjectSerializer`، `EngagementSubjectsWriteSerializer`)، `views.py`
(`AdvisorEngagementSubjectsView` GET/PUT + `StudentSubjectsView` GET — نازک، بدون
import مدلِ حاملِ tenancy)، `urls.py` (`advisory_student_subjects` + `advisory_my_subjects`)،
`admin.py` (ثبتِ `StudentSubject` + `grade` روی `SubjectAdmin` — جای تگ‌زدنِ اونر).

**فرانت** — بسط `services/advisory-service.ts` (`grade`/`gradeLabel` روی
`AdvisorySubject` + سه تایپ + `getEngagementSubjects`/`setEngagementSubjects`/
`getMySubjects`)، `components/advisory/subject-picker-dialog.tsx` (دیالوگِ انتخابگر:
جستجوی فارسی + چیپ‌های پایه + لیستِ چک‌باکس در `ScrollArea` + شمارنده‌ی زنده +
ذخیره‌ی set-replace)، `app/(dashboard)/home/my-subjects-card.tsx` (کارتِ آینه‌ایِ
دانش‌آموز، **«ساکت»** مثل بنر دعوت — تا داده نیامده هیچ‌چیز رندر نمی‌کند)، نصبِ
انتخابگر روی هر ردیفِ روسترِ ACTIVE و کارت زیر `<StatsGrid>` در خانه.

### ۱۱.۲ تصمیم‌ها، انحراف‌ها و ریسک‌های دانسته در گام ۴

| # | موضوع | تصمیم نهایی |
|---|---|---|
| ۱ | **انحراف از §۱: برچسبِ پایه روی `Subject` (تاییدِ صریحِ اونر).** | §۱ «تمام سطوح، بدون پایه‌ی سخت‌کدشده» را قفل کرده بود. اونر پذیرفت که کاتالوگ **تخت** بماند ولی یک **برچسبِ پایه‌ی اختیاری** بگیرد تا انتخابگر یک **فیلترِ راحتی** داشته باشد. قفل نمی‌شکند: درسِ **بی‌برچسب = همه‌ی سطوح** و همیشه نمایش داده می‌شود؛ هیچ «کنکور» یا پایه‌ای سخت‌کد نشده؛ فیلتر صرفاً پیدا‌کردن را آسان می‌کند و چیزی را حذف نمی‌کند. |
| ۲ | **`grade` برچسبِ فیلتر است، نه هویت.** | `grade` عمداً به کلیدهای یکتاییِ `Subject` **افزوده نشد** (هم‌نامیِ ظاهری بین پایه‌ها با نام‌های متمایز حل می‌شود: حسابان ≠ هندسه)؛ `clean()`/`normalized_name` دست‌نخورده (پایه در نرمال‌سازیِ نام نقشی ندارد). ادعای مجاز‌بودنِ درس هم **سمت‌سرور** در `scope.assignable_subjects` تصمیم گرفته می‌شود، نه با این برچسب. |
| ۳ | **درِ نوشتنِ نو + رشدِ آگاهانه‌ی لیستِ معاف.** | `StudentSubject` حاملِ tenancy است؛ طبق قفلِ `test_import_boundaries.py`، ویو/سریالایزر حق import آن را ندارند، پس همه‌ی نوشتن از `services/student_subjects.py` می‌گذرد (خواهرِ `invites.py`). این فایل به `_EXEMPT_FILES` افزوده شد و اَشِرشنِ پین‌شده‌ی «لیستِ معاف تصادفی رشد نکند» + توضیحش به‌روز شد. `StudentSubject` **به `_UNSCOPED` افزوده نشد** — تنها `Subject` بی‌اسکوپ می‌ماند. |
| ۴ | **set-replace با toggleِ `is_active`، نه حذفِ ردیف.** | افزودنِ دوباره‌ی درسی که قبلاً برداشته شده، `is_active` را دوباره True می‌کند به‌جای ساختِ ردیفِ نو. تاریخچه حفظ می‌شود و با فلسفه‌ی خودِ `Subject` («هرگز حذف نکن، غیرفعال کن» — که docstringش از قبل به این PROTECT اشاره داشت) هم‌خط است. |
| ۵ | **فیلترِ نرمِ چندگزینه‌ای (واقعیتِ کنکور).** | چیپ‌های پایه، پایه‌ی خودِ دانش‌آموز را پیش‌انتخاب می‌کنند ولی **چند پایه با هم** قابل انتخاب‌اند (دانش‌آموزِ دوازدهم پایه‌های ۱۰–۱۲ را می‌خواند) و «همه» فیلتر را پاک می‌کند. درسِ بی‌برچسب هرگز پنهان نمی‌شود. برچسبِ پایه از پروفایلِ دانش‌آموز صرفاً برای پیش‌پُرکردنِ چیپ خوانده می‌شود (با گاردِ امن؛ نبودِ پروفایل = بدونِ پیش‌انتخاب). |
| ۶ | **قراردادهای وضعیت حفظ شد.** | engagementِ غریبه/ناموجود → **۴۰۴** (نه ۴۰۳، تا وجودش فاش نشود)؛ PUT روی engagementِ غیرِ ACTIVE → **۴۰۹**؛ id درسِ خارج از `assignable_subjects` → **۴۰۰**؛ نقشِ اشتباه (ادمین هم) → ۴۰۳؛ ناشناس → ۴۰۱؛ دانش‌آموزِ بی‌همکاریِ فعال → **۲۰۰ ساکت** `{active:false, subjects:[]}`. آدرس‌دهی همچنان با **id engagement**، بدون `studentId` روی سیم. |

### ۱۱.۳ وریفای انجام‌شده

- سوئیت اپ `advisory` آفلاین (Postgres/Redis پایین، رسپیِ SQLite+LocMem از memory
  `offline-pytest-without-postgres-redis`) → **۱۹۴ passed** — شاملِ تست‌های نوِ گام ۴
  و تست‌های به‌روزشده‌ی مرزِ import و آلوستِ کاتالوگ.
- `npx tsc --noEmit` → پاک.
- چکِ زنده: به عهده‌ی اونر در دیپلوی (§۵ سطر ۴ / بالای همین بخش).


