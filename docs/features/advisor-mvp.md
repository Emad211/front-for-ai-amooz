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
| دامنه تحصیلی | **برنامه‌ی درسیِ ملی، دیتا‌محور و قابل‌بسط — نه آزمونِ سخت‌کدشده.** پایه (`grade`) و رشته (`major`) **محورهای هویتِ** درس‌اند؛ مجموعه‌ی درسِ هر دانش‌آموز از (پایه × رشته)ی **خودش** مشتق می‌شود و مشاور زیرمجموعه‌ای را فوکوس می‌کند. **رشته از دیتای خودِ دانش‌آموز** می‌آید (نه انتخابِ مشاور/سازمان). این توصیفِ گام ۴ («پایه = برچسبِ فیلتر / بی‌پایه = همه‌ی سطوح») را **وارونه** می‌کند: حالا بی‌پایه = برای هیچ‌کس مشتق نمی‌شود — بازطراحی در §۱۲. |
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
Subject                                     ← لند شد در گام ۲ · grade در گام ۴ · بازطراحیِ ملی (grade+major هویت): §۱۲ · انحراف‌ها: §۹.۲ · §۱۱
  name(fa) · normalized_name(مشتق از name، editable=False، db_index) · is_active
  grade(CharField(2)، '10'|'11'|'12'، null، db_index — بخشی از هویت؛ NULL=درسِ مرده، برای هیچ‌کس مشتق نمی‌شود)
  major(CharField(20)، math|science|humanities، null، db_index — بخشی از هویت؛ NULL=درسِ عمومیِ مشترکِ همه‌ی رشته‌های آن پایه)
  organization FK(null=ملی) · created_at · updated_at · created_by FK SET_NULL
  UniqueConstraint(normalized_name, grade, major, organization) NULLS NOT DISTINCT   ← هویتِ چهارتایی؛ یک constraint جای دو تا (§۱۲)

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

> **بازطراحی شد در §۱۲.** گام ۴ کاتالوگِ **تخت** و سازمان‌محور ساخت؛ §۱۲ آن را به
> **برنامه‌ی درسیِ ملیِ مشتق‌شده از (پایه × رشته)ی خودِ دانش‌آموز** تبدیل کرد. `StudentSubject`
> و منطقِ set-replace **دست‌نخورده**اند؛ تنها **منبعِ کاندیداها** از `assignable_subjects` به
> `curriculum_subjects` عوض شد. ردیف‌های ۱–۲ در §۱۱.۲ زیر (پایه = برچسبِ فیلتر) در §۱۲ **وارونه**
> شده‌اند. این بخش به‌عنوانِ **رکوردِ تاریخیِ** گام ۴ دست‌نخورده نگه داشته می‌شود.

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


---

## ۱۲. بازطراحیِ گام ۴ — کاتالوگِ ملی + مشتق‌گیری از (پایه × رشته) + فوکوسِ مشاور

وضعیت: **کامل، تست‌شده (۲۲۵ passed روی Postgresِ واقعی)، آماده‌ی دیپلوی.** صفر تماس LLM.
این بخش **بازنگریِ گام ۴** است، نه گامی نو در پلنِ ۱۰گامیِ §۵ (گام ۵ همچنان `DailyLog` است).
`StudentSubject` و منطقِ set-replace **دست‌نخورده** ماندند؛ تنها **منبعِ کاندیداها** عوض شد:
از کاتالوگِ تختِ `assignable_subjects` به برنامه‌ی درسیِ مشتق‌شده‌ی `curriculum_subjects`.

### چرا — گپِ منطقی که اونر گرفت
گام ۴ کاتالوگی **تخت** و سازمان‌محور می‌ساخت و مشاور از دلِ آن هر درسی را دستی تیک می‌زد.
تصمیمِ قفل‌شده‌ی اونر این را وارونه کرد: **رشته از دیتای خودِ دانش‌آموز** می‌آید (نه انتخابِ مشاور،
نه تعریفِ سازمان)؛ یک **مجموعه‌ی پایه‌ی ثابتِ ملی** به‌ازای هر (پایه × رشته) برای همه یکسان است؛
سیستم مجموعه‌ی درسِ دانش‌آموز را **خودکار مشتق می‌کند** و مشاور فقط یک **زیرمجموعه را فوکوس** می‌کند.
«ملی + سازمانِ اختیاری»: پایه‌ی ملی برای همه، و سازمان‌ها **می‌توانند** درسِ خصوصی بیفزایند
(`Subject.organization` نگه داشته شد؛ NULL = ملی).

### تغییرِ معناییِ پایه/رشته (وارونه‌کننده‌ی §۱۱.۲ ردیف‌های ۱–۲)
`grade` و `major` حالا **محورهای هویت‌اند**، نه برچسبِ فیلترِ راحتی:
- `grade=NULL` → دیگر «همه‌ی سطوح» نیست؛ یعنی **درسِ مرده/legacy که برای هیچ‌کس مشتق نمی‌شود**.
- `grade` ست، `major=NULL` → درسِ **عمومیِ مشترک** بینِ همه‌ی رشته‌های آن پایه.
- `grade` و `major` هر دو ست → درسِ **مخصوصِ آن رشته**.

### ۱۲.۱ آنچه لند شد

**مدل + مهاجرت** — `models.py`: افزودنِ `major` (+ `SUBJECT_MAJOR_CHOICES`ِ محلی)، بازنگاریِ متنِ
راهنمای `grade` به معنای هویتی، و جایگزینیِ **دو** constraintِ قدیمی (`uniq_advisory_subject_norm_org`
+ پارسلِ `uniq_advisory_subject_norm_global WHERE organization IS NULL`) با **یک**
`UniqueConstraint(normalized_name, grade, major, organization)` با `nulls_distinct=False`
(`UNIQUE NULLS NOT DISTINCT` — جنگو ۵+/PG۱۵+). NULLS NOT DISTINCT هر دو NULL را برابر می‌بیند، پس
یک کلید هم ردیفِ ملی (org NULL) و هم عمومی (major NULL) را پوشش می‌دهد. `clean()` روی هر چهار ستون
دوپلیکیت می‌گیرد؛ `save()` همچنان `normalized_name` را از `name` بازمحاسبه می‌کند (پس بودنش در lookupِ
`get_or_create` انحراف نمی‌سازد). `migrations/0004_...`: RemoveConstraint×۲ + AddField(major) +
AlterField(grade، متنِ نو) + AddConstraint. لیست‌های پایه/رشته **به‌ارزش آینه‌ی
`accounts.StudentProfile`اند** (کپی، نه import — تا وابستگیِ بین‌اپی نسازد).

**اسکوپ** — `services/scope.py`: تابعِ نوِ **`curriculum_subjects(student)`** قلبِ بازطراحی است — از
`studentprofile.grade`/`major`ِ خودِ دانش‌آموز مشتق می‌کند: بی‌پروفایل یا بی‌پایه → `Subject.objects.none()`ِ
ساکت؛ فیلترِ `is_active=True` + `grade` + (`major` دانش‌آموز **یا** `major IS NULL`) + (ملی **یا**
سازمان‌های عضویتِ فعالِ دانش‌آموز). مکملِ نوِ **`student_organization_ids(student)`** (آینه‌ی
`advisor_organization_ids`، فقط عضویتِ STUDENTِ فعال + اشتراکِ فعالِ سازمان). `assignable_subjects(advisor)`
(کاتالوگِ تخت) **باقی ماند ولی دیگر منبعِ پیکر نیست**.

**درِ نوشتن** — `services/student_subjects.py`: `set_engagement_subjects` حالا مقابلِ
`curriculum_subjects(engagement.student)` اعتبارسنجی می‌کند (نه `assignable_subjects`). پارامترِ `advisor`
روی امضا **نگه داشته شد** (پایداریِ محلِ فراخوان + مستندسازیِ اینکه کی عمل می‌کند). پیامِ
`SubjectNotAssignable`: «این درس در برنامه‌ی درسیِ این دانش‌آموز نیست.» set-replace با toggleِ `is_active`
در یک ترنزاکشن دست‌نخورده. `MAX_SUBJECTS_PER_STUDENT = 60`.

**سریالایزر + ویو** — `SubjectSerializer`: `major`/`majorLabel` افزوده شد (کنارِ `grade`/`gradeLabel`).
`StudentSubjectSerializer` عمداً **`major` را فاش نمی‌کند** (دیدِ دانش‌آموز کمینه می‌ماند). GETِ
`AdvisorEngagementSubjectsView` حالا `{studentGrade, studentGradeLabel, studentMajor, studentMajorLabel,
subjects[], selectedSubjectIds[]}` برمی‌گرداند — `subjects` همان querysetِ `curriculum_subjects` است که درِ
نوشتن هم با آن اعتبارسنجی می‌کند، پس پیکر و اعتبارسنج هرگز سرِ «چه چیزی مجاز است» اختلاف پیدا نمی‌کنند.
`_student_axes` پروفایل را دقیقاً مثلِ `accounts` و با گاردِ امن می‌خواند (نبودِ پروفایل = همه‌چیز `None`).

**سیدینگ** — `management/commands/seed_advisory_subjects.py` (تنها نویسنده‌ی کاتالوگِ ملی) +
`data/national_curriculum.json` (عمداً خالی تا گام ۹). فایل را **کامل** اعتبارسنجی می‌کند بعد می‌نویسد
(یک ردیفِ خراب کلِ سید را می‌بندد، بی‌نوشتنِ نصفه)، idempotent با `get_or_create` روی چهارتاییِ هویت
(`organization=None`)، `--dry-run`/`--file`، هشدارِ دوپلیکیتِ درون‌فایلی، پایه اجباری/رشته اختیاری،
بی‌کلابرِ ادیتِ اسمِ ادمین. `_valid_codes` کدهای مجاز را **مستقیم از
`Subject._meta.get_field(...).choices`** می‌خواند — پس گاردِ مرزِ import تنگ می‌ماند (فقط `Subject`
عبور می‌کند، نه تاپلِ choices).

**سیدینگِ خودکار (هات‌فیکسِ دیپلوی ۱۴۰۵/۰۶/۰۱)** — `AdvisoryConfig.ready` سیگنالِ `post_migrate`
را به همان کامند وصل می‌کند؛ چون entrypoint داکر در هر بوت `migrate` می‌زند، کاتالوگ بدون گامِ دستی
همیشه هست (idempotent، پس رایگان است). در تست‌ها `backend/conftest.py` این سیگنال را قطع می‌کند تا
تست‌های APIِ کاتالوگ hermetic بمانند (کامند خودش مستقیم تست می‌شود). نبودِ همین هوک باعث شد
دپلویِ زنده با جدولِ `Subject` خالی شروع کند و مشتقِ (پایه×رشته) برای مشاور و دانش‌آموز همیشه خالی برگردد.

**دیدِ دانش‌آموز — بدونِ تغییر:** `me/subjects/` و کارتِ خانه‌ی دانش‌آموز دست‌نخورده؛ مشتق‌گیریِ خودکار فقط سمتِ مشاور است.

**فرانت** — `services/advisory-service.ts`: `AdvisorySubject` صاحبِ `major`/`majorLabel` شد و متنِ `grade`
به معنای هویتی بازنویسی؛ `EngagementSubjectsResponse` صاحبِ `studentMajor`/`studentMajorLabel` + `subjects[]`؛
docstringِ `getEngagementSubjects` به «برنامه‌ی درسیِ مشتق‌شده‌ی سمت‌سرور». `subject-picker-dialog.tsx` ساده
شد (کاندیداها حالا سمت‌سرور مشتق می‌شوند، پس فیلترِ چیپِ سمت‌کلاینت تا حدِ زیادی حذف شد؛ خالص ۸۵− خط).
`advisor/subjects/page.tsx` هم‌راستا شد.

### ۱۲.۲ نقشه‌ی فلیپِ تست‌ها
- **نو:** `test_curriculum_subjects.py` (۱۴ تست: سه حالتِ هویت، `.none()`ِ ساکت، گیتِ `is_active`، ملی/خصوصی×عضویت/اشتراک/تعلیق).
- **نو:** `test_seed_advisory_subjects.py` (۱۲ تست: validate-first، idempotent-by-identity، بی‌کلابرِ ادیتِ ادمین، major-null=عمومی).
- **به‌روز:** `test_student_subjects.py` (۳۴)، `test_subject_catalog.py` (۳۵)، `test_subjects_api.py` (۱۹).
- گاردِ مرزِ import (`test_import_boundaries.py`) دست‌نخورده: `student_subjects.py` هنوز معاف، `_UNSCOPED={'Subject'}`.

### ۱۲.۳ وریفای انجام‌شده
- کلِ اپ `advisory` روی **Postgresِ واقعی** → **۲۲۵ passed**، صفر تماس LLM.
- `npx tsc --noEmit` → پاک.
- سیدِ دومِ idempotency (۰ ساخته در ران ۲) و جریانِ آنبوردینگ→پیکر→خانه: پس از پُر‌شدنِ دیتا در گام ۹ / اونر در دیپلوی.

### ۱۲.۴ در انتظارِ گام ۹ (دیتا)
لیستِ پایه‌ها + رشته‌ها + درس‌ها هنوز نیامده. با ورودِ دیتا: کدها به choiceها **افزوده** (نه جایگزین)
می‌شوند (+ نگاشتِ `_normalize_student_grade`/`_normalize_student_major`)، `national_curriculum.json` پُر
می‌شود (درس‌های عمومی → `major=null`)، سید اجرا و دراپ‌داونِ آنبوردینگ هم‌راستا می‌شود. کدِ پایه ≤۲ کاراکتر
بماند (وگرنه `max_length` روی **هر دو**ی `StudentProfile.grade` و `Subject.grade` بالا برود).

> **✅ تسویه شد — 2026-08-23، زودتر از گام ۹ (دیتا از اونر رسید).** کدهای پایه `'01'..'09'`
> (همه ≤۲ کاراکتر، بدون مهاجرت max_length) و رشته‌های `theology`/`technical` به هر دو آینه اضافه
> شدند؛ رشته برای پایه‌های ۱۰–۱۲ در آنبوردینگ **اجباری** است؛ پنجرهٔ دبیرستان هر سه پایه را می‌بیند
> (بقیه تک‌پایه)؛ معارف سخت‌گیرانه؛ فنی‌کاردانش موقتاً از کاتالوگ مستثنا ولی کدش معتبر؛ قاعدهٔ
> ادغام هم‌نام‌ها → `major=null`. کاتالوگ ملی: **۱۸۰ ردیف** seed شده (idempotent)، کل مجموعهٔ
> advisory+accounts → **۳۸۰ passed**.



---

## ۱۳. ثبت اجرا — گام ۵ (گزارشِ روزانه‌ی مطالعه · `DailyLog` / `DailyLogItem`)

وضعیت: **کامل، تست‌شده، آماده‌ی دیپلوی.** صفر تماس LLM، صفر Celery.

### ۱۳.۱ آنچه لند شد

**مدل + مهاجرت** — `models.py`: `DailyLog` (یکتای `(engagement, log_date)`؛ `mood` صحیحِ
۱..۵ nullable — NULL یعنی «ثبت نشده» و با بدترینِ حالت یکی نیست؛ `note` TextField با سقفِ
سریالایزری) و `DailyLogItem` (FK به **`StudentSubject`** نه `Subject` — کلیدِ اتصالِ متریکِ
گام ۸ بدونِ مهاجرتِ بعدی؛ PROTECT؛ `actual_minutes` ≤۹۶۰ با CheckConstraint). ثابت‌های کنارِ ستون‌ها:
`MAX_LOG_MINUTES_PER_ITEM=960`، `MAX_LOG_MINUTES_PER_DAY=1440`، `MAX_LOG_NOTE_CHARS=1000`،
`MOOD_MIN=1/MOOD_MAX=5`. `migrations/0005_dailylog_dailylogitem`.

**درِ نوشتن** — `services/daily_logs.py`: `save_day` یک **set-replaceِ یک روز کامل** است؛ ترتیبِ
اعتبارسنجی owner→date→subjects→total پیش از هر نوشتاری (یک درسِ نامعتبر = صفر تغییر)؛ آیتم‌های
`minutes<=0` دراپ می‌شوند؛ آیتم‌های غایب **hard-delete** (عمداً برخلافِ retire نرمِ انتخابِ درس —
آنجا مشاور برنامه‌ای را عوض می‌کند که تاریخچه به آن وصل است؛ اینجا دانش‌آموز گزارشِ خودش را اصلاح
می‌کند)؛ آیتم‌ها upsert تا `created_at` پس از اصلاحِ تایپی بماند؛ `mood`/`note` همیشه overwrite حتی
به `None`/`''`؛ خروجی از `scope.student_day_log` بازخوانده می‌شود تا GET و PUT هر دو از یک مسیر
سریالیزه شوند.

**اسکوپ** — `scope.log_date_window` (جای نوشته‌شده‌ی C3: بازهٔ `[started_on, امروز]` با
`timezone.localdate()`؛ started_onِ آینده به پنجرهٔ بستهٔ «فقط امروز» فرومی‌ریزد نه پنجرهٔ وارونه)،
`student_logs` (prefetch بدونِ فیلترِ is_active — تاریخچه باید بخوانده شود)، `student_day_log`.

**ویو + URL** — `StudentStudyLogView` (GET/PUT `/api/advisory/me/study-log/`، `IsStudentRole`).
GET بی‌مشاور = `200 {"active": false}` ساکت با مجموعه‌کلیدِ کامل؛ GET تاریخِ بدشکل یا بیرونِ بازه =
400؛ PUT بی‌مشاور = 409؛ بدنهٔ PUT کلِ روز است (`date` + `items` اجباری، `mood`/`note` اختیاری)؛
پاسخِ PUT همان payloadِ GET از روی ردیفِ ذخیره‌شده است.

**ادمین** — `DailyLogAdmin` **کاملاً read-only** (+inline آیتم‌ها فقط-دید)؛ D3: هیچ جای ادیتِ
گزارشِ دانش‌آموز توسطِ اپراتور وجود ندارد.

**تست‌ها** — `test_daily_logs.py` (**۲۷ تست**): idempotent بودنِ save دوم + ماندنِ `created_at`
آیتم‌ها؛ دراپِ دقیقهٔ صفر/منفی؛ حذفِ سختِ درسِ غایب از همان روز؛ «روزِ ثبت‌شده اما خالی» ≠
ثبت‌نشده؛ پاک‌شدنِ mood/note؛ `NotTheLogOwner`؛ دو لبهٔ پنجره (آینده/پیش از شروع)؛
`SubjectNotInSelection` (شناسهٔ ناشناخته + درسِ حذف‌شده‌ی مشاور)؛ **ماندنِ دقیقه‌های ثبت‌شدهٔ
درسِ حذف‌شده بینِ روزها** (سناریوی docstring مدل)؛ سقفِ مجموع ۱۴۴۰ (+ مرزِ دقیقاً ۱۴۴۰ مجاز)؛
ماتریس API: GET ساکتِ بی‌مشاور با کلیدهای کامل، تاریخِ پیش‌فرض/صریح، بدشکل ('2026-13-45' و
'yesterday' هر دو 400)، بیرونِ بازه 400، PUT بی‌مشاور 409 با پیام فارسی، دوبلهٔ subjectId 400،
سقف‌های 960/mood/note 400، anon 401 و teacher+advisor 403، و معادلِ چکِ زندهٔ §۵ (PUT سپس GET
همان تاریخ = پایدار).

**فرانت** — `services/advisory-service.ts`: `getMyStudyLog(date?)` / `saveMyStudyLog(body)` با
تایپ‌های wire (`StudyLogPayload`/`StudyLogDay`/`StudyLogItem`). هوکِ نوِ `use-active-advisor`
(promise مشترک در سطح ماژول — مصرف‌کنندگانِ همزمان یک درخواست؛ promise بعد از settle رها می‌شود تا
پذیرشِ دعوت بدون reload در ناوبری بعدی دیده شود؛ خطا = false-safe). صفحهٔ `(dashboard)/study-log`:
چیپ‌های حال‌وهوای ۱..۵ با واژه‌ها «بد / نه چندان / متوسط / خوب / عالی» (صعودی؛ در RTL از راست
شروع می‌شود) + گزینهٔ «ثبت نکردم» (= null)؛ ردیفِ دقیقه به تفکیک درس با چیپ‌های سریع و clamp به
۹۶۰؛ ردیف‌های فقط-خواندنیِ «حذف‌شده از فهرست» برای آیتم‌های `isSelected:false` تا مجموع صادق بماند؛
مجموع زنده با هشدار رنگی نزدیک سقف؛ شمارندهٔ یادداشت ۱۰۰۰ کاراکتری؛ استپرِ تاریخِ جلالی قفل‌شده به
`[minDate,maxDate]`؛ **ذخیره = set-replace و re-render کامل همهٔ state از پاسخ سرور** (never from
local guesses). ورودی شرطیِ منوی «گزارش روزانه» در pill nav هدر + نوار پایین موبایل — فقط با
مشاور فعال؛ هنگام load هیچ رندر نمیشود (بدون فلش برای بقیه).

### ۱۳.۲ وریفای انجام‌شده
- کلِ اپ `advisory` → **۲۵۳ passed** (۲۲۶ قبلی + ۲۷ نو)، صفر تماس LLM/Celery.
- `npx tsc --noEmit` → پاک (exit 0).
- `next build` → سبز؛ روت `/study-log` در خروجی تولید شد.
- چکِ زندهٔ §۵ سطر ۵ (ثبتِ امروز → refresh → ماندن): همتای خودکارش در تستِ API سبز است؛ اجرای
  دستی به عهدهٔ اونر در دیپلوی.


---

## ۱۴. بازطراحی گام‌های ۶–۸ — افق متغیر به‌جای هفتهٔ شنبه‌ای (تصمیم اونر، 2026-08-23)

> **این بخش تصمیم قفل‌شدهٔ «مدل زمانی» در §۱ را وارونه می‌کند** — همان کاری که §۱۲ با گام ۴ کرد.
> برنامه‌ریزی دیگر «هفتگیِ لنگر به شنبه» نیست: مشاور برای هر برنامه **تاریخ شروعِ آزاد** و
> **طول دلخواه** انتخاب می‌کند — چیپ‌های ۷/۱۴/۳۰ روز یا «دلخواه» تا سقف **۹۰ روز**. فیدِ مطالعه هم
> به‌جای پنجرهٔ ثابت ۷روزه، همین گزینه‌ها + حالت «از شروع» را دارد. جدول‌ها چون هنوز مهاجرت
> نداشتند، از `WeeklyPlan/WeeklyPlanItem` به **`StudyPlan/StudyPlanItem`** تغییر نام یافتند
> (آخرین فرصت تمیز). تکرارِ خودکار برنامه‌ها در MVP نیست — پایان هر بازه = مشاور پلن بعدی را می‌سازد.
> ردیف‌های گام ۶–۸ در §۵ و بلوک جداول §۲ با این بخش بازنویسی معنا می‌شوند؛ متن قبلی رکورد تاریخی است.

### ۱۴.۱ مدل داده (سه جدول نو — migration 0006)

```
StudyPlan                                    ← افق متغیر · گام ۷ (بازطراحی §۱۴)
  engagement FK PROTECT                      ← حامل tenancy مثل بقیه
  start_date DateField                       ← آزاد؛ ≥ started_on (قاعده C3 برای نوشتن)
  duration_days PositiveSmallInt             ← CheckConstraint 1..90
  status DRAFT|PUBLISHED                     ← همان چرخهٔ §۵ گام ۷
  created_at · updated_at
  PartialUniqueConstraint: فقط «یک» DRAFT per engagement   ← اسلات پیش‌نویس
  Index (engagement, status, start_date)
  ⚠ عدم‌همپوشانی با PUBLISHED ها قانونِ سرویس است (مقایسه با ردیف‌های همسایه؛ constraint نمی‌شود).

StudyPlanItem                                ← کلید اتصال S8 مثل DailyLogItem → StudentSubject
  plan FK PROTECT related_name='items'
  day_offset SmallInt                        ← CheckConstraint 0..89 ؛ سقفِ واقعی < duration_days در سرویس
  student_subject FK PROTECT                 ← همان تصمیم DailyLogItem؛ PROTECT
  planned_minutes PositiveSmallInt           ← CheckConstraint 1..960 (هم‌مقیاس با actual)
  UniqueConstraint (plan, day_offset, student_subject)

AdvisoryAccessLog                            ← D4: از لحظهٔ روشن‌شدن خواندن نوشته می‌شود؛ backfill ندارد
  reader FK User SET_NULL null               ← append-only؛ هیچ API نمی‌نویسد/نمی‌خواندش
  engagement FK PROTECT · action CharField(32) ('study_feed_view') · accessed_at auto db_index
  Indexes (engagement,-accessed_at) · (reader,-accessed_at) · ادمین کاملاً read-only
```

### ۱۴.۲ اندپوینت‌ها و قرارداد wire (کلیدها camelCase)

مشاور (`IsAdvisorUser`؛ pk = engagement id؛ حلّ از `scope.advisor_engagement` → None ⇒ **404 نه 403**):
| متد مسیر | رفتار |
|---|---|
| `GET students/<pk>/study-feed/?days=7\|14\|30\|all` | فید مطالعه؛ پارامتر نامعتبر ⇒ 400 «بازه باید یکی از ۷، ۱۴، ۳۰ یا all باشد.»؛ روی موفقیت **دقیقاً یک** `AdvisoryAccessLog(action='study_feed_view')` |
| `PUT students/<pk>/study-plan/draft` | upsert اسلات پیش‌نویس (set-replace کامل بدنه) |
| `POST students/<pk>/study-plan/draft/publish` | اعتبارسنجی مجدد → PUBLISHED |
| `POST students/<pk>/study-plan/<plan_id>/unpublish` | اهرم rollback §۵: برگشت به DRAFT |
| `GET students/<pk>/study-plans` | همه وضعیت‌ها، صعودی start_date |

دانش‌آموز (`IsStudentRole`): `GET me/plans` → `{plans:[…]}` فقط PUBLISHED نزولی؛ بی‌مشاور = ساکت `{plans:[]}`.

شکل فید:
```jsonc
{ "studentName": "...", "range": {"from":"YYYY-MM-DD","to":"YYYY-MM-DD"},
  "days": [ {"date","totalMinutes","mood","note",
             "items":[{"subjectId","name","minutes"}]} ],      // فقط روزهای ثبت‌شده، صعودی
  "plans": [ {"id","startDate","endDate","durationDays","status":"PUBLISHED",
              "items":[{"dayOffset","date","subjectId","name","plannedMinutes"}]} ] } // تقاطع با بازه
```
`from`: عددی ⇒ `max(started_on, today-(days-1))` (کلمپ C3)؛ all ⇒ started_on؛ `to`=امروز.

بدنه draft: `{startDate, durationDays, items:[{dayOffset, subjectId, plannedMinutes}]}`؛ پاسخ PUT/PUBLISH/UNPUBLISH = شکل PlanOut همان پلن.

### ۱۴.۳ قواعد درِ نوشتن (`services/study_plans.py` — معافِ گارد مرز)

ترتیب اعتبارسنجی mirrorِ `save_day`: مالکیت مشاور → شروع (`start_date >= started_on` else 400
«تاریخ شروع نمی‌تواند پیش از شروع همکاری باشد.») → طول (1..90 else «طول برنامه باید بین ۱ و ۹۰ روز
باشد.») → آیتم‌ها: `day_offset < duration_days` («روز N خارج از طول برنامه است.»)، موضوع جزو
انتخاب فعال («این درس در فهرست درس‌های شما نیست.»)، دقیقه 1..960، دوبله `(day_offset,subject)`
400 («برای هر روز و درس فقط یک ردیف بفرستید.»). سپس atomic: upsert اسلات DRAFT + set-replace
آیتم‌ها (پیش‌نویس تاریخچه ارزشمند ندارد — برخلاف DailyLogItem مستند شود).

**publish**: پیش‌نویس موجود نیست ⇒ 404؛ خالی ⇒ 400 «برنامهٔ خالی قابل انتشار نیست.»؛
اعتبارسنجی مجددِ آیتم‌ها مقابلِ انتخاب‌های فعلی (درس حذف‌شده وسط راه ⇒ 400)؛ **عدم‌همپوشانی**
با سایر PUBLISHED ها: تقاطع `[start, start+duration-1]` — لمسِ لبه‌ها (پایان==شروع دیگری)
مجاز؛ تخلف ⇒ 400 «این بازه با برنامهٔ منتشرشدهٔ دیگری همپوشانی دارد.»؛ فلیپ زیر
`select_for_update`.

### ۱۴.۴ ماتریس تست حداقلی (§6 ادامه دارد)
idempotence پیش‌نویس + جایگزینی wholesale؛ تک-پیش‌نویسی؛ publish→me/plans می‌بیند؛ unpublish→
غیب می‌شود؛ ردّ همپوشانی + مجوزِ لمسِ لبه؛ خالی/درس-حذف‌شده هنگام publish؛ شروع پیش از همکاری؛
طول 0/91 رد و 1/90 قبول؛ offset==duration رد / duration-1 قبول؛ موضوع غیرفعال؛ دوبله؛ دقیقه
0/961؛ مشاور دیگر 404؛ دانش‌آموز→403؛ anon→401؛ فید: چهار حالت days، کلمپ C3 (شروع دیروز ⇒
from=started_on)، فقط روزهای ثبت‌شده صعودی، فیلتر تقاطع پلن‌ها، **AccessLog: دقیقاً +۱ ردیف per
خواندن موفق با reader/action درست، و هیچ ردیفی روی 400/404/403**.

### ۱۴.۵ فرانت (گام‌های ۶+۷)
صفحهٔ جزئیات دانش‌آموز مشاور `(advisor)/advisor/students/[id]`: چیپ‌های بازهٔ فید
(۷/۱۴/۳۰/از شروع)، لیست روزها (مجموع/حال‌وهوا/نوت/آیتم‌ها) و پلنر: انتخابگر تاریخ جلالی +
چیپ‌های طول ۷/۱۴/۳۰/دلخواه≤۹۰ + ادیتور ردیفی {روز(۱..N), درس(select از فعال‌ها), دقیقه} +
ذخیره پیش‌نویس/انتشار/لغو انتشار. دانش‌آموز: کارت «برنامه مطالعه» در home (نزدیک‌ترین PUBLISHED
جاری/آینده با آیتم‌ها).


---

## ۱۵. ثبت اجرا — گام‌های ۶+۷ (فید مطالعه + برنامهٔ افق‌متغیر)

وضعیت: **کامل، تست‌شده، آمادهٔ دیپلوی.** صفر تماس LLM/Celery. طبق §۱۴ ساخته شد.

### ۱۵.۱ آنچه لند شد (بک‌اند)
`migrations/0006`: سه جدول §۱۴.۱ با همهٔ constraint/indexها (اسلاتِ تک-DRAFT جزئی؛ بازهٔ
day_offset 0..89 با سقف واقعی در سرویس). `scope.py`: چهار خوانِ نو (`feed_date_range` با کلمپ C3،
`advisor_feed_logs` صعودی، `advisor_plans`، `student_published_plans` نزولی).
`services/study_plans.py` (درِ نوشتن معافِ گارد مرز): `_validate_body` با همان ترتیب save_day
(شروع→طول→offset→موضوع→دقیقه→دوبله) پیش از هر نوشتاری؛ `save_draft` با قفل ردیف engagement
(مسابقهٔ دو PUT پشت partial unique می‌بَرد) و hard-replace آیتم‌ها؛ `publish_draft` زیر
select_for_update با ۴۰۴/خالی/درسِ کهنه/همپوشانیِ اکید (لمسِ لبه مجاز)؛ `unpublish_plan`
اهرمِ rollback — برخورد با اسلات DRAFT به نفعِ rollback حل می‌شود (پیش‌نویسِ هیچ‌وقت-دیده‌نشده
حذف؛ اول آیتم‌ها چون FK پروتکت است)؛ `record_study_feed_view` تنها روی ۲۰۰ موفق یک ردیف D4.
ویوها: شش کلاس نو (فید/draft/publish/unpublish/list/me-plans)؛ فید payload + AccessLog «بعد از
payload، قبل از پاسخ». ادمین: `AdvisoryAccessLogAdmin` کاملاً read-only.

### ۱۵.۲ فرانت
`advisory-service.ts`: تایپ‌های §۱۴.۲ + شش تابع. صفحهٔ نو `(advisor)/advisor/students/[id]`
(روتر داینامیک): هدر با نام دانش‌آموز (از رستر)، کارت **گزارش مطالعه** (چیپ‌های ۷/۱۴/۳۰/از شروع؛
روزها با تاریخ جلالی، مجموع فارسی، چیپ واژه‌ای mood، نوت، ردیف درس-دقیقه) و کارت **برنامه‌ریزی**
(pیکر جلالی date-only نو با react-day-picker/persian + minDate=startedOn، چیپ‌های طول + دلخواه≤۹۰،
ادیتور ردیفی با اعتبارسنجی کلاینت هم‌پیام سرور، مجموع زنده، ذخیره/انتشار [اول save سپس publish]
/لغو انتشار فقط روی منتشرشده‌ها). لینک «گزارش و برنامه» از رستر. کارت «برنامه مطالعه» در home
دانش‌آموز (جاری یا نزدیک‌ترین آینده؛ quiet-null).

### ۱۵.۳ وریفای انجام‌شده
- کل اپ advisory → **۳۰۰ passed** (۲۵۳ قبلی + ۴۷ نو: ماتریس کامل §۱۴.۴ شامل کلمپ C3، لمسِ لبه،
  حسابداری AccessLog [+۱ موفق / صفر روی خطا]).
- `npx tsc --noEmit` پاک؛ `next build` سبز با روتر نو `/advisor/students/[id]`.
- چک زنده §۵ (فید مشاور دیروز را می‌بیند؛ انتشار → دانش‌آموز می‌بیند): همتای خودکار در تست‌ها
  سبز؛ اجرای دستی به عهدهٔ اونر در دیپلوی.

## ۱۶. فاز ری‌استارت — گسترش کامل بر اساس دفترچۀ کاغذی (لندشده 2026-08-26)

وضعیت: **کامل، تست‌شده، پوش‌شده به main.** صفر تماس LLM/Celery. تنها منبع حقیقت این فاز:
[`docs/features/advisor-restart-plan.md`](./advisor-restart-plan.md) — ۱۳ گام، ۱۲ اصل قفل
(صفر LLM ق۱، هفته شنبه‌محور ق۴ با فرمول واحد در `services/calendar.py`، بدون jdatetime سمت
سرور ق۵، 404-نه-403 ق۶، ویوهای جدید در ماژول‌های جدید ق۱۱).

### ۱۶.۱ آنچه لند شد (خلاصۀ موج‌ها)
- **موج ۱:** غنی‌سازی DailyLog (`day_goal/motivation_note/tests_taken/test_percent`، مایگریشن
  0008) + تب‌بندی `/advisor/students/[id]` به ۷ تب query-param محور با Suspense.
- **موج ۲:** منبع مطالعۀ هر درس (`StudentSubject.source`، 0009) + غنی‌سازی ردیف برنامه
  (`StudyPlanItem.topic/unit_label/test_minutes/mastery_color` + `StudyPlan.day_notes`، 0010) +
  فلگ جبران‌نشده در فید مشاور.
- **موج ۳:** فرم شناخت (`AdvisoryIntakeProfile/Class`، 0011)، ارزیابی هفتگی ۱۵ معیاری
  (`WeeklyAssessment`، 0012 — کانونیک در `services/assessments.py`)، طرح تماس هفتگی
  (`WeeklyCallLog`، 0013 — چرخش موضوع پیش‌فرض بر شمارۀ هفته).
- **موج ۴:** نمرات آزمون (`StudyExamScore`، 0014 — سقف ۴۰) + تحلیل کارنامه
  (`StudyExamAnalysis/Row/Note`، 0015 — set-replace کامل rows/notes).
- **موج ۵:** ماه در یک نگاه (`MonthlyOutlook/Entry/Strategy`، 0016 — کلید Gregorian month_start)
  + چالش ۷ روزه (`StudyChallenge/Day`، 0017 — end_date سرورمحور start+6، سقف ۳ فعال، گذار وضعیت
  یک‌طرفه).
- **موج ۶:** همین سند + یادداشت ریلیز.

ماژول‌های سرویس جدید (همه در درِ معافِ گارد مرزها): `calendar, intake, assessments, calls,
exam_records, monthly, challenges`. ویوهای جدید: `views_intake.py`, `views_monthly.py`,
`views_exams.py` (طبق ق۱۱ — `views.py` رشد نکرد).

### ۱۶.۲ وریفای انجام‌شده
- هر موج قبل از پوش: کل سوئیت advisory سبز + `npx tsc --noEmit` پاک (پیشروی تست‌ها: 326 → 553).
- اسموک زندهٔ پروداکشن-مانند روی لوکال پس از هر موج (راندتریپ کامل هر ماژول + پیام‌های خطای فارسی
  پین‌شده + آینه‌های quiet دانش‌آموزی).
- دو رگرسیون hydration حل شد حین تست لوکال: `<a>` تودرتو در هدر لندینگ و `<button>` تودرتو در
  پیکر دروس.





