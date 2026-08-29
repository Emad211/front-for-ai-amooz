# پلن «ری‌استارت» — گسترش فیچر مشاور بر اساس دفترچۀ کاغذی ماهانه

وضعیت: **اجرا‌شدهٔ کامل — همهٔ ۱۳ گام لند شد (2026-08-26)** · منبع: PDF «ری‌استارت — مجلۀ مشاوره و برنامه‌ریزی» (۴۴ صفحه، ماه مهر) + وضعیت لندشدهٔ S1–S9 · پیش‌نیاز: `docs/features/advisor-mvp.md` (تنها منبع حقیقت MVP)

### ثبت اجرا (موج‌به‌موج)

| موج | گام‌ها | کامیت‌ها |
|---|---|---|
| ۱ | ۱۱ (تب‌بندی) + ۱ (چکینگ روزانه) | `b6403bb` + `e97cd49` |
| ۲ | ۳ (منبع درس) + ۴ (غنی‌سازی برنامه) | `ff69cba` (اتمیک — فایل مشترک) |
| ۳ | ۲ (شناخت) + ۷ (ارزیابی) + ۱۰ (تماس) | `310f2d4` بک + `93df30d` فرانت |
| ۴ | ۵ (نمرات) ← ۶ (تحلیل کارنامه) | `cf5b8ac` بک + `aad37b1` فرانت |
| ۵ | ۸ (ماه) + ۹ (چالش) | `d662902` بک + `820f45a` فرانت |
| ۶ | ۱۳ (ریلیز) | همین کامیت |

وریفای نهایی: **553 تست advisory سبز** (از 326)، `tsc --noEmit` پاک در هر موج، اسموک زندهٔ
پروداکشن-مانند روی لوکال پس از هر موج. یادداشت ریلیز:
[`docs/releases/2026-08-26-advisor-restart.md`](../releases/2026-08-26-advisor-restart.md).

این سند تنها منبع حقیقت فازِ گسترش است. کد و این سند با هم لند می‌شوند. هر گام یک واحدِ کامیت‌شدنی کامل است (بک‌اند + فرانت + تست + داکیومنت). شماره‌گذاری گام‌ها بر اساس دامنه است، نه ترتیب اجرا — ترتیب اجرا در §۶ (موج‌ها) آمده.

---

## ۰. خلاصهٔ اجرایی

دفترچۀ کاغذی «ری‌استارت» یک **چرخهٔ ماهانهٔ مشاوره** است: پروفایل شناخت ← هدف‌گذاری ماه ← ۴ هفتهٔ (برنامهٔ هفتگی + چکینگ روزانه + ارزیابی مشاور + تحلیل آزمون) ← نمرات ماهانه ← چالش ۷ روزه ← طرح تماس.

سیستم فعلی فقط حلقهٔ **هفته** را دارد (برنامهٔ هفتگی، لاگ روزانه، تعهد). این پلن ۱۳ گام دارد که:

- **۴ گام** موجود را غنی می‌کنند (چکینگ روزانه، ردیف برنامه، منبع درس، تب‌بندی UI)
- **۷ ماژول جدید** می‌سازند (شناخت، نمرات آزمون، تحلیل کارنامه، ارزیابی هفتگی، ماه در یک نگاه، چالش ۷ روزه، طرح تماس)
- **۲ گام** آینه‌های دانش‌آموزی و ریلیز را می‌بندند

حجم کل: ~۹ مایگریشن جدید، ~۱۷ روت جدید، ~۸ کارت فرانت جدید. **صفر تماس LLM. صفر پکیج جدید. صفر متغیر محیطی جدید.**

---

## ۱. اصول قفل‌شده (تغییرناپذیر — نقض هرکدام باگ است)

| # | اصل | جزئیات |
|---|---|---|
| ق۱ | **صفر LLM در advisory** | هیچ گام این پلن تماس LLM یا Celery ندارد؛ همه‌چیز CRUD سنکرون است. |
| ق۲ | **tenancy فقط از `scope.py`** | هر ویو فقط `advisor_engagement` / `student_active_engagement` / `visible_*` می‌خواند. گاردِ `test_import_boundaries.py` باید با هر فایل سرویس جدید به‌روز شود (لیست allowlist آن تست). |
| ق۳ | **جهت import** | `advisory` از `accounts`/`organizations`/`classes` import می‌کند؛ **`classes` هرگز از `advisory`**. |
| ق۴ | **هفته لنگرِ شنبه** | `week_start = d - timedelta(days=(d.weekday() + 2) % 7)`. این فرمول یک‌بار در `services/calendar.py` (جدید، گام ۱) نوشته می‌شود و همهٔ مدل‌های هفته‌محور از همان می‌خوانند — نه از کپی محلی. |
| ق۵ | **بدون jdatetime سمت سرور** | ذخیره همیشه Gregorian. برچسب جلالی فقط فرانت (`date-fns-jalali` موجود). «ماه» در MonthlyOutlook فقط یک کلید تاریخ میلادی است (اولین روزِ میلادیِ آن ماه جلالی) — محاسبه‌اش وظیفهٔ فرانت است. |
| ق۶ | **۴۰۴ نه ۴۰۳** | همکاریِ غایب/متعلق به مشاور دیگر ⇒ ۴۰۴. دانش‌آموز بدون مشاور فعال: نوشتن ⇒ ۴۰۹؛ خواندن ⇒ ۲۰۰ quiet (`active:false` یا لیست خالی). |
| ق۷ | **on_delete** | engagement ریشهٔ مالکیت است ⇒ همهٔ فرزندان جدید `CASCADE` به engagement. مرجع‌های بیرونی (`User` نویسنده) ⇒ `SET_NULL`. |
| ق۸ | **وایر camelCase؛ کد/کامنت انگلیسی؛ کپی کاربر فارسی** | مثل بقیهٔ advisory. |
| ق۹ | **هر گام با تست لند می‌شود** | pytest + model-bakery، صفر توکن. ماتریس دسترسی (مالک/غریبه/نقش اشتباه) برای هر روت جدید اجباری. |
| ق۱۰ | **بدون پکیج/متغیر محیطی جدید** | هیچ گامی `requirements.txt` یا `.env` را تغییر نمی‌دهد. |
| ق۱۱ | **`views.py` بلاک نشود** | فایل الان ~۹۴۰ خط است. ویوهای جدید در ماژول‌های جدید: `views_intake.py`، `views_exams.py`، `views_monthly.py` — و در `urls.py` همان اپ include می‌شوند. |
| ق۱۲ | **متریک تعهد دست نمی‌خورد** | adherence و moodAverage (S8) سرِ جایشان؛ گام‌های جدید فقط شاخهٔ اطلاعاتی اضافه می‌کنند. |

---

## ۲. وضعیت فعلی (لندشده — مبنای تغییر)

### بک‌اند (`backend/apps/advisory/` — مایگریشن تا `0007`)

| موجودیت | فایل | نکته |
|---|---|---|
| `Subject` (name, normalized_name, grade `'01'..'12'`, major math/science/humanities/theology, organization) | `models.py` | هویت چهارتایی؛ کاتالوگ ملی ۱۸۰ ردیفی با auto-seed در `apps.py` (post_migrate) سید می‌شود؛ در تست‌ها قطع است (conftest.py) |
| `AdvisoryEngagement` (advisor/student/mode/org/status PENDING→ACTIVE/ENDED) | `models.py` | یگانه‌ی ACTIVE per student |
| `StudentSubject` (engagement, subject, is_active — set-replace) | `models.py` + `services/student_subjects.py` | `MAX_SUBJECTS_PER_STUDENT = 60` |
| `WeeklyPlan` / `WeeklyPlanItem` (day_offset 0..6، planned_minutes 1..960، DRAFT/PUBLISHED، overlap-guard) | `models.py` + `services/study_plans.py` | اسلات DRAFT یگانه |
| `DailyLog` (log_date، mood 1..5، note) / `DailyLogItem` (student_subject، actual_minutes 0..960) | `models.py` + `services/daily_logs.py` | پنجرهٔ نوشتن = `[started_on, today]` (قانون C3 در `scope.log_date_window`) |
| `AdvisoryAccessLog` | `models.py` | هر خواندن feed یک ردیف |
| درِ tenancy | `services/scope.py` | `curriculum_subjects(student)` = مشتق (grade×major) با باند مشترک `HIGH_SCHOOL_GRADES=['10','11','12']` |
| ویوها | `views.py` (~۹۴۰ خط) | الگو: `_resolve_engagement_or_404` + `IsAdvisorUser` / `IsStudentRole` |
| تست‌ها | ۱۵ فایل `test_*.py` (۳۲۶ تست سبز) | — |

### فرانت

| موجود | مسیر |
|---|---|
| سرویس | `frontend/src/services/advisory-service.ts` (همهٔ روت‌ها **با** trailing slash — رگرسیون ۴۰۵ قفل شده) |
| صفحات مشاور | `app/(advisor)/advisor/{page,students/page,students/[id]/page,subjects/page}.tsx` |
| کامپوننت‌های مشاور | `components/advisory/{subject-picker-dialog,advisor-invite-banner}.tsx` و `components/advisory/study-plan/{study-feed-card,study-planner-card,jalali-date-picker}.tsx` |
| سمت دانش‌آموز | `app/(dashboard)/study-log/page.tsx`، `components/dashboard/study-log/*`، `components/dashboard/home/{study-plan-card,my-subjects-card}.tsx` |
| کتابخانه | `lib/adherence.ts`، `lib/persian-digits.ts`، `lib/persian-search.ts`، `lib/date-utils.ts` |

---

## ۳. خارج از دامنهٔ این فاز (صریح)

1. **والدین / رابط آموزشی** — طبق §۱ اسپک MVP قفل است. آیتم‌های روزانهٔ والدینِ PDF (غر زدن، تلویزیون و…) در ارزیابی هفتگیِ مشاور ادغام شده‌اند (گام ۷).
2. **نقش «پشتیبان آموزشی»** — نقش جدید نمی‌سازیم؛ وظایف پشتیبان به مشاور می‌رسد.
3. **OCR پاسخ‌برگ ۳۰۰ سوالی (ص۴۳-۴۴)** — ورود کارنامه با عکس/OCR یعنی تماس provider؛ ممنوع در این فاز. ثبت دستی نمرات (گام ۵) جایگزین است. ایدهٔ فاز بعد: اتصال به زیرساخت exam-prep.
4. **مقالات آموزشی (ص۳۹-۴۱)** — محتوای ثابت؛ بعد از این فاز به‌صورت صفحات استاتیک لند می‌شود، نه داخل advisory.
5. **جبران خودکار عقب‌افتادگی‌ها** (انتقال خودکار ردیف نخوانده به هفتهٔ بعد) — در این فاز فقط **نمایش** «جبران‌نشده» در فید (گام ۴). انتقال خودکار فاز بعد.

---

## ۴. قراردادهای سراسری

### ۴.۱ نقشهٔ روت (همه زیر `/api/advisory/`)

| الگو | متد | نقش | توضیح |
|---|---|---|---|
| `students/<int:pk>/intake/` | GET, PUT | مشاور | شناخت دانش‌آموز؛ PUT = set-replace کامل (کلاس‌ها هم) |
| `me/intake/` | GET, PUT | دانش‌آموز | فرم خودِ دانش‌آموز (PUT بدون مشاور فعال ⇒ ۴۰۹) |
| `students/<int:pk>/exam-scores/` | GET, POST | مشاور | لیست/ایجاد (سقف ۴۰ ردیف به‌ازای engagement) |
| `students/<int:pk>/exam-scores/<int:score_id>/` | PATCH, DELETE | مشاور | ویرایش جزئی/حذف |
| `me/exam-scores/` | GET | دانش‌آموز | آینهٔ quiet (لیست خالی بدون مشاور) |
| `students/<int:pk>/exam-analyses/` | GET, POST | مشاور | لیست/ایجاد تحلیل |
| `students/<int:pk>/exam-analyses/<int:analysis_id>/` | GET, PUT, DELETE | مشاور | PUT = set-replace کامل rows+notes |
| `me/exam-analyses/` | GET | دانش‌آموز | آینهٔ quiet — همهٔ تحلیل‌های مشاورِ فعالِ خودش |
| `students/<int:pk>/weekly-assessments/` | GET, PUT | مشاور | `?week_start=YYYY-MM-DD`؛ PUT = upsert یگانه بر (engagement, week_start) |
| `students/<int:pk>/call-logs/` | GET, PUT | مشاور | لیست + upsert |
| `students/<int:pk>/monthly-outlooks/<date:month_start>/` | GET, PUT | مشاور | PUT = upsert کامل (entries + strategies) |
| `me/monthly-outlooks/<date:month_start>/` | GET | دانش‌آموز | آینهٔ quiet |
| `students/<int:pk>/challenges/` | GET, POST | مشاور | لیست/ایجاد (سقف ۳ چالش ACTIVE) |
| `students/<int:pk>/challenges/<int:challenge_id>/` | GET, PATCH, DELETE | مشاور | PATCH = وضعیت/متادیتا؛ روزها روت جدا |
| `students/<int:pk>/challenges/<int:challenge_id>/days/` | PUT | مشاور | set-replace کامل روزها |
| `me/challenges/` | GET | دانش‌آموز | چالش‌های engagement فعال خودش |
| `me/challenges/<int:challenge_id>/days/` | PUT | دانش‌آموز | فقط goal/summary روزها (set-replace محدود) |

قواعد: همهٔ مشاور-روت‌ها `[IsAuthenticated, IsAdvisorUser]` + الگوی `_resolve_engagement_or_404`؛ همهٔ me-روت‌ها `[IsAuthenticated, IsStudentRole]` + `student_active_engagement`. `extend_schema` روی هر ویو (مثل بقیهٔ advisory برای drf-spectacular).

### ۴.۲ قواعد وایر

- کلیدها camelCase؛ تاریخ‌ها ISO `YYYY-MM-DD`؛ زمان‌ها `HH:MM`.
- هر PUT «set-replace کامل» است (الگوی subjects/study-log موجود) — نه patch ضمنی.
- خطاها همیشه `{"detail": "<فارسی>"}`: 400 اعتبارسنجی، 404 غریبه/غایب، 409 تعارض وضعیت.
- هر لیستِ خوراکِ پیکر/فرم unpaginated است؛ لیست‌های تاریخی نزولی بر تاریخ.

### ۴.۳ مایگریشن‌ها (شماره‌ی پیشنهادی؛ نهایی با ترتیب لند)

`0008` dailylog-enrichment · `0009` intake · `0010` studentsubject-source · `0011` plan-item-enrichment · `0012` exam-score · `0013` exam-analysis · `0014` weekly-assessment · `0015` monthly-outlook · `0016` challenge · `0017` call-log. همه در اپ `advisory`؛ هیچ مایگریشن cross-app.

### ۴.۴ فایل‌های سرویس جدید (هرکدام باید به allowlist `test_import_boundaries.py` اضافه شوند)

`services/calendar.py` (گام ۱) · `services/intake.py` (گام ۲) · `services/exam_records.py` (گام ۵+۶) · `services/assessments.py` (گام ۷) · `services/monthly.py` (گام ۸) · `services/challenges.py` (گام ۹) · `services/calls.py` (گام ۱۰).

---

## ۵. گام‌ها

### گام ۱ — غنی‌سازی چکینگ روزانه (PDF ص۸-۹) · حجم: S

**هدف:** هر لاگ روزانه علاوه بر mood/دقیقه، «هدف روز، جمله انگیزشی، تعداد تست، درصد آزمون» را نگه دارد.

**بک‌اند:**
- `services/calendar.py` (جدید): `week_start_of(d: date) -> date` (فرمول ق۴) + `ensure_saturday(d)` (validator مشترک). ثبت در allowlist تست مرزها.
- مایگریشن `0008` روی `DailyLog`:
  - `day_goal` CharField(200, blank=True, default='') — «هدف‌گذاری برای امروز»
  - `motivation_note` CharField(200, blank=True, default='') — «شعار/جمله انگیزشی»
  - `tests_taken` PositiveIntegerField(default=0) — «تعداد تست»
  - `test_percent` PositiveSmallIntegerField(null=True, blank=True, validators=[0..100]) — «درصد آزمون»
- «رضایت» فیلد جدید **نمی‌گیرد** — همان `mood` موجود است (نگاشت در کامنت مدل نوشته شود).
- `services/daily_logs.py::save_day`: پذیرش ۴ فیلد جدید در همان set-replace موجود؛ اعتبارسنجی bounds در serializer.
- `serializers.py`: خروجی روز (StudyLogDay معادل) + کلیدهای وایر جدید: `dayGoal`, `motivationNote`, `testsTaken`, `testPercent`.

**فرانت:**
- `app/(dashboard)/study-log/page.tsx` + `components/dashboard/study-log/*`: سه ورودی جدید در فرم روز (هدف، جمله، تعداد تست، درصد) — درصد با ورودی عددی ۰-۱۰۰.
- `components/advisory/study-plan/study-feed-card.tsx`: هر روزِ فید علاوه بر mood/مجموع، `testsTaken`/`testPercent` را نشان دهد (چیپ کوچک؛ فقط اگر > 0 / non-null).

**تست:** `test_daily_logs.py` — گسترش: (a) ذخیرهٔ ۴ فیلد جدید و بازگشتشان، (b) ردِ test_percent خارج از ۰-۱۰۰ با 400، (c) set-replace قبلی نشکند، (d) پنجرهٔ C3 سرِ جایش.

**پذیرش:** دانش‌آموز می‌تواند هدف/جمله/تست/درصد روز را ثبت کند؛ فید مشاور هر دو را نشان می‌دهد؛ ۳۲۶ تست موجود + جدیدها سبز.

---

### گام ۲ — فرم شناخت دانش‌آموز / Intake (PDF ص۱) · حجم: M

**هدف:** معادل دیجیتال «اطلاعات فردی دانش‌آموز» — مدرسه، شهر، معدل سال گذشته، رشته/دانشگاه هدف، مؤسسۀ آزمون، میانگین مطالعۀ روز آزاد، جدول کلاس‌ها.

**بک‌اند:**
- مایگریشن `0009` — دو مدل:
  - `AdvisoryIntakeProfile`: `engagement` OneToOne(AdvisoryEngagement, CASCADE, related_name='intake') · `school` CharField(120, blank, default='') · `city` CharField(60, blank, default='') · `last_gpa` DecimalField(4,2, null, blank, validators=[0..20]) · `target_major` CharField(120, blank) · `target_university` CharField(120, blank) · `mock_exam_institute` CharField(120, blank) · `free_day_minutes` PositiveIntegerField(null, blank, validators=[0..1440]) · `updated_by` FK(User, SET_NULL, null) · `updated_at` auto.
  - `AdvisoryIntakeClass`: `intake` FK CASCADE related_name='classes' · `name` CharField(120) · `teacher` CharField(120, blank) · `weekday` PositiveSmallIntegerField(choices 0..6، 0=شنبه) · `start_time` TimeField(null) · `end_time` TimeField(null) · `order` PositiveSmallIntegerField(default=0). **سقف ۱۰ ردیف** در سرویس (PDF ۷ دارد).
- `services/intake.py`: `get_or_init_intake(engagement)` + `replace_intake(engagement, payload, actor)` — set-replace کامل شامل بازسازی `classes`؛ اعتبارسنجی: weekday ∈ 0..6، end>start وقتی هر دو هستند، سقف ردیف‌ها.
- `views_intake.py` (جدید): `AdvisorIntakeView` (GET/PUT) + `StudentIntakeView` (GET/PUT). PUT دانش‌آموز بدون engagement فعال ⇒ 409 «ابتدا مشاور خود را تأیید کنید.»
- روت‌ها در `urls.py`: `students/<int:pk>/intake/` و `me/intake/`.

**وایر:** `IntakePayload { school, city, lastGpa, targetMajor, targetUniversity, mockExamInstitute, freeDayMinutes, classes: [{name, teacher, weekday, startTime, endTime, order}] }`.

**فرانت:**
- `components/advisory/intake-card.tsx` (مشاور) — فرم کامل + جدول کلاس‌ها (افزودن/حذف ردیف، سقف ۱۰ با پیام فارسی)؛ در تب «شناخت» (گام ۱۱).
- `components/dashboard/advisory/my-intake-card.tsx` (دانش‌آموز) — همان فرم، فقط وقتی advisor فعال است؛ جایگذاری در home کنار my-subjects-card.

**تست:** `test_intake.py` (جدید) — ماتریس دسترسی (مشاور مالک 200 / مشاور غریبه 404 / دانش‌آموز دیگر 403 روی روت مشاور)، set-replace کلاس‌ها، سقف ۱۰ ⇒ 400 با detail فارسی، weekday نامعتبر ⇒ 400، PUT دانش‌آموز بدون مشاور ⇒ 409، gpa خارج از 0..20 ⇒ 400.

**پذیرش:** مشاور و دانش‌آموز هر دو می‌توانند فرم را کامل کنند؛ آخرین نویسنده در `updated_by` می‌ماند؛ خواندنِ غریبه ۴۰۴ است.

---

### گام ۳ — منبع مطالعۀ هر درس (PDF ص۵) · حجم: S

**هدف:** برای هر درسِ انتخابی دانش‌آموز، «منبع» ثبت شود (کتاب درسی / جزوه معلم / فیلم / جزوه کنکور / سایر).

**بک‌اند:**
- مایگریشن `0010` روی `StudentSubject`:
  - `source` CharField(max_length=20, null=True, blank=True, choices=[TEXTBOOK 'کتاب درسی', TEACHER_BOOKLET 'جزوه معلم', VIDEO 'فیلم', KONKUR_BOOKLET 'جزوه/دفترنامۀ کنکور', OTHER 'سایر'])
- `services/student_subjects.py::set_engagement_subjects`: امضای جدید `set_engagement_subjects(engagement, subject_ids, *, advisor, sources=None)` — `sources` دیکشنری `{subject_id: code}`؛ کد نامعتبر ⇒ `SubjectNotAssignable`-مانند جدید `InvalidSource` (400). نبودِ کلید = source همان ردیف دست نمی‌خورد (backward compatible).
- `AdvisorEngagementSubjectsView` (PUT): بدنه `{subjectIds, sources?}` — کلید sources اختیاری.
- سریالایز خروجی هر دو سمت (مشاور/دانش‌آموز) + کلید `source`.

**فرانت:**
- `components/advisory/subject-picker-dialog.tsx`: کنار هر ردیفِ تیک‌خورده یک Select کوچک منبع (پیش‌فرض «—»)؛ ذخیره، `sources` را فقط برای ردیف‌های انتخابی می‌فرستد.
- `components/dashboard/home/my-subjects-card.tsx`: نمایش بج منبع کنار هر درس (اگر ست شده).

**تست:** `test_student_subjects.py` — گسترش: ذخیره/به‌روزرسانی منبع، کد نامعتبر ⇒ 400، نبودِ sources = بدون تغییر، منبعِ درسِ حذف‌شده با ردیف غیرفعال می‌ماند (تاریخ نمی‌میرد).

**پذیرش:** مشاور می‌تواند منبع هر درس را در پیکر ست کند؛ دانش‌آموز آن را می‌بیند؛ PUT قدیمی (بدون sources) بدون خطا کار می‌کند.

---

### گام ۴ — غنی‌سازی ردیف برنامه و نوت روز (PDF ص۵ و ص۷) · حجم: M

**هدف:** ردیف برنامه = «موضوع + واحد + دقیقۀ مطالعه + زمان تست + کد رنگ تسلط»؛ هر روزِ برنامه = یادداشت مدرسه/امتحان/کلاس/پیش‌خوانی.

**بک‌اند:**
- مایگریشن `0011`:
  - `WeeklyPlanItem` + `topic` CharField(200, blank, default='') · `unit_label` CharField(60, blank, default='') · `test_minutes` PositiveIntegerField(null, blank, validators=[0..480]) · `mastery_color` CharField(6, null, blank, choices=[RED, YELLOW, GREEN]).
  - `WeeklyPlan` + `day_notes` JSONField(default=dict, blank=True) — شکل مجاز: `{"<0..6>": {"school": str≤120, "exams": str≤120, "konkurClass": str≤120, "preReading": str≤120}}`؛ کلیدهای خارج از این شکل ⇒ 400 در سرویس (validator دستی در `study_plans.save_draft`، نه JSON schema).
- `services/study_plans.py::save_draft`: پذیرش فیلدهای جدید هر ردیف (اختیاری، default حفظ رفتار فعلی) + `dayNotes` در سطح برنامه.
- سریالایز `PlanOut`/`PlanItemOut` + کلیدهای `topic`, `unitLabel`, `testMinutes`, `masteryColor` و `dayNotes` روی برنامه.
- **فید (ص۵):** `AdvisorStudyFeedView` خروجی `days` هر روز علاوه بر items، ردیف‌های «جبران‌نشده» را نشان دهد: هر آیتم برنامه‌ای که `plannedMinutes>0` و `actual==0` در همان روز ⇒ فلگ `uncompensated:true` (فقط نمایش؛ §۳-۵).

**فرانت:**
- `study-planner-card.tsx`: هر ردیف = روز + درس + موضوع + واحد + دقیقه + زمان تست + Select رنگ (🔴🟡🟢)؛ بخش جمع‌شونده «یادداشت روزها» (۷ ردیف × ۴ فیلد).
- `study-feed-card.tsx`: نمایش topic/unit/color-dot و بج «جبران‌نشده» روی روزهایی که آیتم انجام‌نشده دارند.
- `components/dashboard/home/study-plan-card.tsx` (دانش‌آموز): نمایش masteryColor به‌صورت نقطهٔ رنگی کنار درس.

**تست:** `test_study_plans.py` — گسترش: ذخیره/بازخوانی فیلدهای جدید، `day_notes` با کلید '7' ⇒ 400، رفتار قدیمی (بدون فیلدهای جدید) بدون تغییر، `uncompensated` فقط برای planned>0/actual=0.

**پذیرش:** مشاور می‌تواند برنامه را با موضوع/واحد/زمان تست/رنگ بنویسد؛ فید عقب‌افتادگی را برجسته می‌کند؛ خروجی قدیمی کلاینت‌ها نشکند (کلیدهای جدید additive).

---

### گام ۵ — نمرات آزمون (PDF ص۴۲) · حجم: M

**هدف:** جدول «نمرات کسب‌شده»: هر آزمون/امتحان با نوع، درصد، تراز، تاریخ و ارزیابی مشاور.

**بک‌اند:**
- `services/exam_records.py` (جدید) + مایگریشن `0012` — مدل:
  - `StudyExamScore`: `engagement` FK CASCADE related_name='exam_scores' · `title` CharField(120) (نام درس/آزمون) · `subject` FK(Subject, PROTECT, null, blank) (لینک اختیاری به کاتالوگ) · `exam_kind` CharField(10, choices=[SCHOOL 'مدرسه', PERSONAL 'شخصی', CLASS_C 'کلاس', ONLINE 'آنلاین', NATIONAL 'کنکور کشوری', ADVISOR 'آزمون مشاور']) · `exam_date` DateField · `score_percent` DecimalField(5,2, validators=[0..100]) · `tara` IntegerField(null, blank) (تراز کل) · `advisor_rating` CharField(10, null, blank, choices=[EXCELLENT 'عالی', GOOD 'خوب', FAIR 'متوسط', WEAK 'ضعیف']) · `advisor_note` TextField(blank, default='') · `created_by` FK(User, SET_NULL, null) · `created_at/updated_at`.
  - `Index(engagement, -exam_date)` · **سقف ۴۰ ردیف** در سرویس (`MAX_EXAM_SCORES = 40`؛ عبور ⇒ 400 «سقف ثبت نمرات پر شده است.»).
- `views_exams.py` (جدید): `AdvisorExamScoresView` (GET list نزولی بر exam_date / POST)، `AdvisorExamScoreDetailView` (PATCH/DELETE)، `StudentExamScoresView` (GET quiet).
- روت‌ها: طبق §۴.۱.

**وایر:** `ExamScore { id, title, subjectId?, subjectName?, examKind, examDate, scorePercent, tara?, advisorRating?, advisorNote }`.

**فرانت:**
- `components/advisory/exam-scores-card.tsx` (مشاور، تب «آزمون‌ها»): جدول + فرم افزودن (Select نوع آزمون و ارزیابی، DatePicker جلالی، ورودی درصد/تراز) + ویرایش inline + حذف با تأیید.
- `components/dashboard/advisory/my-exam-scores-card.tsx` (دانش‌آموز): فقط خواندنی، نزولی بر تاریخ.

**تست:** `test_exam_records.py` (جدید) — ماتریس دسترسی کامل، سقف ۴۰ ⇒ 400، score_percent خارج 0..100 ⇒ 400، exam_kind نامعتبر ⇒ 400، DELETE فقط مشاور مالک، آینهٔ دانش‌آموز بدون مشاور ⇒ `{active:false, scores:[]}`.

**پذیرش:** مشاور نمرات را ثبت/ویرایش/حذف می‌کند؛ دانش‌آموز فقط می‌بیند؛ ترتیب نزولی تاریخ.

---

### گام ۶ — تحلیل آزمون و کارنامه (PDF ص۱۷-۲۰) · حجم: L

**هدف:** پس از هر آزمون: تحلیل درس‌به‌درس (غلط/نزده/شک‌دار + علت)، متریک‌های کارنامه (تراز/رتبه/درصدها)، و «نکات مهم آزمون» به تفکیک سؤال.

**بک‌اند:**
- مایگریشن `0013` — سه مدل:
  - `StudyExamAnalysis`: `engagement` FK CASCADE related_name='exam_analyses' · `exam_number` PositiveSmallIntegerField(null, blank) · `exam_date` DateField(null, blank) · `grade_band` CharField(10, null, blank, choices=[G10 'دهم', G11 'یازدهم', G12S1 'دوازدهم نیمسال اول', G12S2 'دوازدهم نیمسال دوم']) · `total_tara` IntegerField(null, blank) · `national_rank` / `region_rank` / `city_rank` IntegerField(null, blank) · `highest_percent` / `lowest_percent` DecimalField(5,2, null, blank) · `tara_delta` SmallIntegerField(null, blank) (±) · `advisor_report` TextField(blank, default='') · `created_at/updated_at`.
  - `StudyExamAnalysisRow`: `analysis` FK CASCADE related_name='rows' · `subject_name` CharField(120) (متن آزاد — هر مؤسسه اسم خودش) · `wrong_count` / `skipped_count` PositiveIntegerField(default=0) · `doubtful_total` / `doubtful_wrong` / `doubtful_skipped` / `doubtful_correct` PositiveIntegerField(default=0) · `cause_note` CharField(300, blank, default='').
  - `StudyExamAnalysisNote`: `analysis` FK CASCADE related_name='notes' · `question_number` PositiveIntegerField(validators=[1..300]) · `subject_name` CharField(120) · `note` TextField. UniqueConstraint(analysis, question_number).
- `services/exam_records.py`: `create_analysis` / `replace_analysis(analysis, payload)` (set-replace کامل rows+notes در یک تراکنش) / `delete_analysis`. اعتبارسنجی: doubtful_* ≤ همدیگر منطقی (wrong+skipped+correct ≤ total) ⇒ 400 فارسی.
- `views_exams.py`: `AdvisorExamAnalysesView` (GET/POST) · `AdvisorExamAnalysisDetailView` (GET/PUT/DELETE) · `StudentExamAnalysesView` (GET quiet، نزولی exam_date).
- روت‌ها: طبق §۴.۱.

**وایر:** `ExamAnalysis { id, examNumber?, examDate?, gradeBand?, totalTara?, nationalRank?, regionRank?, cityRank?, highestPercent?, lowestPercent?, taraDelta?, advisorReport, rows: [{subjectName, wrongCount, skippedCount, doubtfulTotal, doubtfulWrong, doubtfulSkipped, doubtfulCorrect, causeNote}], notes: [{questionNumber, subjectName, note}] }`.

**فرانت:**
- `components/advisory/exam-analysis-card.tsx` (مشاور، تب «آزمون‌ها»): لیست تحلیل‌ها + فرم ایجاد/ویرایش: بخش کارنامه (تراز/رتبه‌ها/درصدها/دلتا + گزارش متنی)، جدول ردیف‌های درس (افزودن/حذف ردیف)، جدول نکات سؤال‌به‌سؤال.
- `components/dashboard/advisory/my-exam-analyses-card.tsx` (دانش‌آموز): فقط خواندنی — کارنامه + گزارش مشاور + نکات.

**تست:** `test_exam_records.py` — گسترش: set-replace کامل rows/notes، سؤال تکراری در notes ⇒ 400، شمارهٔ سؤال 0 یا 301 ⇒ 400، ماتریس دسترسی، آینهٔ quiet، PUT غریبه ⇒ 404.

**پذیرش:** چرخۀ کامل «ثبت تحلیل ← ویرایش ← حذف» برای مشاور؛ دانش‌آموز تحلیل مشاور خودش را می‌بیند؛ هیچ روت دانش‌آموزیِ نوشتن روی analysis وجود ندارد.

---

### گام ۷ — ارزیابی هفتگی مشاور (PDF ص۱۰) · حجم: M

**هدف:** معادل «ارزیابی هفتگی تیم مشاوره» — ۱۵ معیار نمره ۱-۵ برای هر هفته (شنبه-محور) + جمع‌بندی متنی مشاور.

**بک‌اند:**
- مایگریشن `0014` — مدل:
  - `WeeklyAssessment`: `engagement` FK CASCADE related_name='weekly_assessments' · `week_start` DateField (validator: `ensure_saturday` از `calendar.py`) · `scores` JSONField (شکل: `{"<code>": 1..5}` — همهٔ ۱۵ کلید اجباری) · `advisor_summary` TextField(blank, default='') · `created_by` FK SET_NULL · `created_at/updated_at` · UniqueConstraint(engagement, week_start).
- ثابت کانونی معیارها در `services/assessments.py` (تک‌منبع؛ لیبل فارسی برای فرانت هم از همینجا سریالایز می‌شود):

```python
WEEKLY_ASSESSMENT_CRITERIA = [
    ('plan_order',         'نظم و هماهنگی در اجرای برنامه'),
    ('exam_discipline',    'رعایت دقیق آزمون‌ها'),
    ('planning_accuracy',  'دقت در نوشتن برنامه و گزارش‌کار'),
    ('daily_log_discipline','ثبت روزانهٔ چکینگ'),
    ('study_hours',        'ساعت مطالعه نسبت به برنامه'),
    ('test_count',         'تست‌زنی نسبت به هدف'),
    ('review_discipline',  'مرور و جبران عقب‌افتادگی‌ها'),
    ('class_attendance',   'حضور در کلاس‌ها'),
    ('school_homework',    'تکالیف مدرسه'),
    ('sleep_routine',      'روتین خواب'),
    ('mood_level',         'سطح روحی و انگیزه'),
    ('focus_quality',      'کیفیت تمرکز در مطالعه'),
    ('stress_management',  'مدیریت استرس'),
    ('screen_time',        'کنترل فضای مجازی و تلویزیون'),
    ('home_environment',   'شرایط محیط منزل'),
]
```
  (فهرست از PDF + تکمیل معیارهای ناخوانا؛ مالک می‌تواند قبل از لند بازنویسی کند — بعد از لند تغییر کد = مایگریشن دیتا.)
- `services/assessments.py`: `upsert_weekly_assessment(engagement, week_start, scores, summary, actor)` — اعتبارسنجی: week_start شنبه، scores کلیدهای دقیقاً ۱۵گانه با int 1..5 ⇒ وگرنه 400 با نام معیار خطا.
- `views_monthly.py` یا `views_intake.py`؟ — در `views_monthly.py` (مشترک با گام ۸): `AdvisorWeeklyAssessmentsView` (GET list نزولی week_start / PUT upsert با `?week_start=`).
- **سمت دانش‌آموز: هیچ روت.** ارزیابی داخلی مشاور است (قفل این گام).

**فرانت:**
- `components/advisory/weekly-assessment-card.tsx` (مشاور، تب «ارزیابی»): انتخاب هفته (DatePicker محدود به شنبه‌ها یا auto-anchor)، ۱۵ ردیف (لیبل فارسی + ۵ دکمهٔ امتیاز)، جمع‌بندی متنی، ذخیره (upsert). میانگین هفته به‌صورت عدد بزرگ بالای کارت.

**تست:** `test_assessments.py` (جدید) — upsert دوباره روی همان هفته = آپدیت نه ردیف جدید، scores ناقص ⇒ 400 با نام معیار، week_start غیرشنبه ⇒ 400، ماتریس دسترسی، نبودِ روت دانش‌آموزی (تست منفی: GET me ⇒ 404).

**پذیرش:** مشاور برای هر هفته یک ارزیابی کامل ثبت می‌کند؛ دوباره‌ذخیره آپدیت است؛ دانش‌آموز به هیچ‌وجه دسترسی ندارد.

---

### گام ۸ — ماه در یک نگاه + استراتژی‌های ماه (PDF ص۳-۴) · حجم: M

**هدف:** تقویم ماهانه (مناسبت + تقویم تحصیلی + کارها برای هر روز) و ۴ استراتژی ماه با «مجری» (مشاور/دانش‌آموز).

**بک‌اند:**
- مایگریشن `0015` — سه مدل:
  - `MonthlyOutlook`: `engagement` FK CASCADE related_name='monthly_outlooks' · `month_start` DateField (کلید؛ UniqueConstraint(engagement, month_start)) · `created_at/updated_at`.
  - `MonthlyOutlookEntry`: `outlook` FK CASCADE related_name='entries' · `date` DateField · `event` CharField(120, blank) (مناسبت) · `academic_note` CharField(200, blank) (تقویم تحصیلی) · `tasks` TextField(blank) · UniqueConstraint(outlook, date).
  - `MonthlyStrategy`: `outlook` FK CASCADE related_name='strategies' · `position` PositiveSmallIntegerField(validators=[1..10]) · `title` CharField(120) · `executor` CharField(10, choices=[ADVISOR 'مشاور', STUDENT 'دانش‌آموز']) · `body` TextField(blank) · UniqueConstraint(outlook, position).
- `services/monthly.py`: `upsert_outlook(engagement, month_start, payload)` — set-replace کامل entries+strategies در یک تراکنش؛ entry.date خارج از بازهٔ ماه month_start **مجاز** است (تقویم تحصیلی مرزی دارد) ولی هشدار نمی‌دهیم — قید نمی‌شود (ساده نگه دار).
- `views_monthly.py`: `AdvisorMonthlyOutlookView` (GET/PUT بر `<date:month_start>`) · `StudentMonthlyOutlookView` (GET quiet).
- روت‌ها: طبق §۴.۱.

**وایر:** `MonthlyOutlook { monthStart, entries: [{date, event, academicNote, tasks}], strategies: [{position, title, executor, body}] }`.

**فرانت:**
- `components/advisory/monthly-outlook-card.tsx` (مشاور، تب «ماه»): انتخاب ماه جلالی (date-fns-jalali → month_start میلادی)، نمای لیستی ۳۰ روزه (هر ردیف: تاریخ جلالی + سه فیلد)، و ۴ اسلات استراتژی با Select مجری.
- `components/dashboard/advisory/my-monthly-outlook-card.tsx` (دانش‌آموز): فقط خواندنی.

**تست:** `test_monthly.py` (جدید) — upsert دوباره = replace کامل (entry حذف‌شده واقعاً حذف شود)، position تکراری ⇒ 400، executor نامعتبر ⇒ 400، ماتریس دسترسی، آینهٔ quiet.

**پذیرش:** مشاور تقویم و استراتژی‌های ماه را می‌نویسد؛ دانش‌آموز می‌بیند؛ کلید ماه بین فرانت و بک یک تاریخ میلادی ISO است.

---

### گام ۹ — چالش ۷ روزه (PDF ص۳۷) · حجم: M

**هدف:** ساخت چالش هفت‌روزه با هدف/روتین/ناظر و پر کردن روزبه‌روزِ آن توسط دانش‌آموز.

**بک‌اند:**
- مایگریشن `0016` — دو مدل:
  - `StudyChallenge`: `engagement` FK CASCADE related_name='challenges' · `title` CharField(120) · `goal_text` TextField(blank) (تعریف و هدف) · `daily_routine` CharField(200, blank) · `execution_note` CharField(200, blank) (نوع اجرا) · `observer` CharField(120, blank) (مجری و ناظر) · `problem_target` TextField(blank) (مشکل و نتیجهٔ مدنظر) · `start_date` DateField · `end_date` DateField (= start+6؛ CheckConstraint) · `status` CharField(10, choices=[ACTIVE 'فعال', DONE 'پایان‌یافته', CANCELLED 'لغوشده'], default=ACTIVE) · `created_at/updated_at`.
  - `StudyChallengeDay`: `challenge` FK CASCADE related_name='days' · `day_number` PositiveSmallIntegerField(validators=[1..7]) · `goal` CharField(200, blank) (هدف‌گذاری روز) · `summary` TextField(blank) (خلاصۀ کارها/مشکلات/نتیجه) · UniqueConstraint(challenge, day_number).
- `services/challenges.py`: `create_challenge` (end_date را سرور می‌سازد = start+6؛ ورودی end نادیده) · `replace_days(challenge, payload, actor)` — مشاور: همهٔ فیلدها؛ دانش‌آموز: فقط goal/summary (فیلد دیگر ⇒ 400 «فقط هدف و خلاصهٔ روز را می‌توانید ثبت کنید.») · `set_status` (ACTIVE→DONE/CANCELLED؛ برگشت ممنوع ⇒ 409) · **سقف ۳ چالش ACTIVE** ⇒ 400.
- `views_monthly.py` (یا `views_intake.py` — تصمیم اجرا: `views_monthly.py`): `AdvisorChallengesView` (GET/POST) · `AdvisorChallengeDetailView` (GET/PATCH/DELETE) · `AdvisorChallengeDaysView` (PUT) · `StudentChallengesView` (GET) · `StudentChallengeDaysView` (PUT).
- روت‌ها: طبق §۴.۱.

**فرانت:**
- `components/advisory/challenge-card.tsx` (مشاور، تب «چالش‌ها»): فرم ایجاد + لیست چالش‌ها با وضعیت + ویرایش روزها + دکمه‌های پایان/لغو.
- `components/dashboard/advisory/my-challenge-card.tsx` (دانش‌آموز، home): چالش فعال + ۷ روز (هدف/خلاصهٔ هر روز، فقط روزهای ≤ امروز قابل نوشتن — اعتبارسنجی فرانت + سرویس).

**تست:** `test_challenges.py` (جدید) — end_date سرورمحور (=start+6)، سقف ۳ فعال ⇒ 400، دانش‌آموز فقط goal/summary (تلاش برای تغییر بقیه ⇒ 400)، day_number خارج 1..7 ⇒ 400، ماتریس دسترسی، status برگشتی ⇒ 409.

**پذیرش:** چرخۀ کامل «مشاور می‌سازد ← دانش‌آموز روزبه‌روز پر می‌کند ← مشاور می‌بیند/پایان می‌زند».

---

### گام ۱۰ — طرح تماس هفتگی (PDF ص۳۸) · حجم: S

**هدف:** چک‌لیست تماس‌های هفتگی مشاور با موضوع پیش‌فرض هر هفته (نسخهٔ بدون والدین).

**بک‌اند:**
- مایگریشن `0017` — مدل:
  - `WeeklyCallLog`: `engagement` FK CASCADE related_name='call_logs' · `week_start` DateField (ensure_saturday؛ UniqueConstraint(engagement, week_start)) · `done` BooleanField(default=False) · `call_date` DateField(null, blank) · `topic` CharField(200, blank, default='') · `note` TextField(blank, default='') · `updated_at`.
- پیش‌فرض موضوع بر اساس شمارۀ هفتهٔ engagement (هفتهٔ n از started_on): هفتهٔ ۱ «ارائۀ برنامۀ هفتگی و هدف‌گذاری»، ۲ «انجام دقیق برنامه و گزارش‌کار»، ۳ «تحلیل آزمون و برنامۀ جبرانی»، ۴+ «ارزیابی ماهانه و نقاط قوت/ضعف» — ثابت `DEFAULT_CALL_TOPICS` در `services/calls.py` (چرخه‌ای mod 4). موضوعِ ذخیره‌شده همیشه بر پیش‌فرض می‌برد.
- `services/calls.py`: `list_call_logs(engagement)` (۴ هفتۀ اخیر + پرکردن هفته‌های غایب به‌صورت مجازی done=False) · `upsert_call_log(...)`.
- ویو در `views_monthly.py`: `AdvisorCallLogsView` (GET/PUT با `?week_start=`).
- سمت دانش‌آموز: هیچ روت (داخلی مشاور — مثل گام ۷).

**فرانت:**
- `components/advisory/call-log-card.tsx` (مشاور، تب «ارزیابی» زیر کارت گام ۷): ۴ ردیف هفته (لیبل جلالی هفته، موضوع پیش‌فرض قابل‌ویرایش، تیک انجام‌شدن + تاریخ + یادداشت).

**تست:** `test_calls.py` (جدید) — upsert، پیش‌فرض موضوع per-week-index، week_start غیرشنبه ⇒ 400، ماتریس دسترسی، نبودِ روت دانش‌آموزی.

**پذیرش:** مشاور وضعیت تماس هفتگی هر دانش‌آموز را در یک نگاه می‌بیند و ثبت می‌کند.

---

### گام ۱۱ — تب‌بندی صفحۀ جزئیات دانش‌آموز (IA) · حجم: S

**هدف:** صفحۀ `advisor/students/[id]` با ۷ کارت جدید شلوغ می‌شود — قبل از لندِ کارت‌ها، ساختار تب‌بندی شود.

**فرانت (فقط فرانت):**
- `app/(advisor)/advisor/students/[id]/page.tsx`: هدر + نوار تب (`?tab=` با `useSearchParams`؛ default = `feed`):
  - `feed` «گزارش» → StudyFeedCard
  - `plan` «برنامه» → StudyPlannerCard
  - `exams` «آزمون‌ها» → ExamScoresCard + ExamAnalysisCard (گام ۵-۶)
  - `intake` «شناخت» → IntakeCard (گام ۲)
  - `assess` «ارزیابی» → WeeklyAssessmentCard + CallLogCard (گام ۷ و ۱۰)
  - `month` «ماه» → MonthlyOutlookCard (گام ۸)
  - `challenges` «چالش‌ها» → ChallengeCard (گام ۹)
- تا وقتی کارت یک تب لند نشده، تب با empty-state «به‌زودی» رندر می‌شود (نه حذف تب) — ترتیب لند را آزاد می‌کند.
- تب‌ها با `Link`/`router.replace` (scroll حفظ)؛ موبایل: نوار تب افقیِ اسکرول‌شونده RTL.

**تست:** `lib/auth-routing.test.ts` سبز می‌ماند؛ تست فرانت جدید لازم نیست (رفتار URL ساده است) ولی یک smoke دستی در PR توضیح داده می‌شود.

**پذیرش:** هیچ کارتی بالای ۱۰۰٪ ارتفاع صفحه انباشته نمی‌شود؛ deep-link به هر تب کار می‌کند.

---

### گام ۱۲ — آینه‌های دانش‌آموزی · حجم: M

**هدف:** دانش‌آموز همهٔ چیزهایی را که مشاور برایش می‌نویسد می‌بیند (به‌جز ارزیابی و تماس که داخلی‌اند).

**فرانت:**
- Home دانش‌آموز (`app/(dashboard)/home/page.tsx`) — ترتیب کارت‌ها بعد از study-plan-card موجود:
  1. `my-exam-scores-card.tsx` (گام ۵) — «نمرات آزمون‌های من»
  2. `my-exam-analyses-card.tsx` (گام ۶) — «تحلیل کارنامۀ من» (فقط گزارش مشاور + متریک‌ها)
  3. `my-challenge-card.tsx` (گام ۹) — «چالش فعال»
  4. `my-intake-card.tsx` (گام ۲) — «شناخت من» (فرم قابل ویرایش)
  5. `my-monthly-outlook-card.tsx` (گام ۸) — «برنامۀ ماه»
- همه: بدون مشاور فعال ⇒ رندر نمی‌شوند (الگوی `useActiveAdvisor` موجود)؛ با مشاور ⇒ fetch quiet.
- `advisory-service.ts`: به‌ازای هر آینه یک متد + type (فهرست دقیق در هر گام آمده).

**تست:** فرانت — `tsc` + lint سبز؛ رفتار quiet با mock payload بد (Array.isArray guards مثل رگرسیون t.find) در کامپوننت‌ها رعایت شود.

**پذیرش:** دانش‌آموز با مشاور فعال، هر ۵ کارت را می‌بیند؛ بدون مشاور هیچ‌کدام ظاهر نمی‌شود؛ هیچ فرمی بدون ۴۰۹-هندل نیست.

---

### گام ۱۳ — مستندات، ریلیز، دیپلوی · حجم: S

- `docs/features/advisor-mvp.md`: بخش «§۱۵ — فاز ری‌استارت» + لینک به همین سند؛ هر گام هنگام لند، ردیف خودش را در جدول همین سند تیک می‌زند (ستون وضعیت اضافه شود هنگام شروع موج ۱).
- `docs/releases/YYYY-MM-DD-advisor-restart.md`: فهرست مایگریشن‌ها، روت‌های جدید، نکتۀ دیپلوی (مایگریشن‌ها خودکار در entrypoint اجرا می‌شوند؛ auto-seed دست نمی‌خورد).
- `docs/reference/` در صورت وجود صفحۀ advisory، به‌روز شود.
- وریفای نهایی قبل از push: `python -m pytest backend/apps/advisory/ -q` (همه سبز) + `cd frontend && npx tsc --noEmit` + `npm run lint` (اگر ابزار lint درست شده بود؛ در غیر این صورت ثبت known-issue).
- دیپلوی: push به `main` (fast-forward از برنچ کاری، الگوی همیشگی) → Darkube rebuild → smoke دستی: ساخت چالش، ثبت نمره، ارزیابی هفته، آینه‌های دانش‌آموزی.

---

## ۶. موج‌بندی و اجرای موازی (ترتیب اجرا)

هر موج = یک یا دو گامِ قابل‌اجرای موازی با ایجنت‌ها. هر گام یک PR/کامیت کامل است (بک+فرانت+تست+داک).

| موج | گام‌ها | چرا این ترتیب | ایجنت پیشنهادی |
|---|---|---|---|
| **موج ۱** | گام ۱۱ (تب‌بندی) + گام ۱ (چکینگ روزانه) | خانه را قبل از اسباب‌کشی مرتب کن؛ گام ۱ کوچک و مستقل | دو ایجنت موازی: `visual-engineering` (تب) + `deep` (گام ۱) |
| **موج ۲** | گام ۳ (منبع درس) + گام ۴ (ردیف برنامه) | هر دو روی مدل‌های موجود؛ فایل‌های مشترک کم | دو ایجنت موازی `deep` (بک+فرانت هر گام کامل) |
| **موج ۳** | گام ۲ (شناخت) + گام ۷ (ارزیابی) + گام ۱۰ (تماس) | سه ماژول کوچک مستقل؛ allowlist مرزها یک‌بار در موج ۲ آپدیت می‌شود و بقیه الگو می‌گیرند | سه ایجنت موازی `deep` |
| **موج ۴** | گام ۵ (نمرات) → گام ۶ (تحلیل) | ۶ روی ۵ سوار است (همان فایل سرویس/ویو/تست) — **ترتیبی**، نه موازی | یک ایجنت `deep` پیوسته (session continuity) |
| **موج ۵** | گام ۸ (ماه) + گام ۹ (چالش) | مستقل از هم | دو ایجنت موازی `deep` |
| **موج ۶** | گام ۱۲ (آینه‌ها) + گام ۱۳ (ریلیز) | بعد از لند همهٔ محتوا | ایجنت `visual-engineering` + خودِ اورکستراتور برای ریلیز |

قاعدهٔ تعارض: دو ایجنتِ یک موج هرگز فایل مشترک ندارند — اگر شد، آن دو گام ترتیبی شوند. `advisory-service.ts` و `urls.py` نقاط ادغام‌اند؛ merge ترتیبی موج‌ها (نه هم‌زمان به main).

---

## ۷. ریسک‌ها و نکات

| ریسک | پالایش |
|---|---|
| `test_import_boundaries.py` با سرویس‌های جدید بشکند | هر موج، allowlist را در همان گام آپدیت کند — در تعریف «تمام‌شده»ی هر گام هست. |
| شلوغی `advisory-service.ts` (الان ~۵۶۰ خط) | بعد از موج ۵، اگر از ~۱۲۰۰ خط گذشت، به `advisory-service/{index,exams,monthly,...}.ts` بشکند (تصمیم آن‌موقع؛ الان نه). |
| تغییر فهرست ۱۵ معیار بعد از لند | کد معیارها پایدار است (کلید JSON)؛ فقط لیبل فارسی عوض شود بی‌هزینه است؛ افزودن/حذف معیار = مایگریشن دیتا + مهاجرت scores. |
| تقویم جلالی فرانت و month_start | فقط `date-fns-jalali` (وابستگی موجود)؛ هرگز تاریخ جلالی به سرور فرستاده نشود — همیشه ISO میلادی. |
| رگرسیون ۴۰۵ | هر روت جدید در سرویس فرانت **با** trailing slash؛ در review چک شود (کامنت گارد سرِ اولین مورد مانده است). |
| حجم `views.py` | ویوهای جدید فقط در ماژول‌های جدید (ق۱۱)؛ `_resolve_engagement_or_404` از `views.py` import می‌شود (خودش جابجا نشود در این فاز). |
| تست‌های موجود | هر گام قبل از push: کل `backend/apps/advisory/` سبز + `tsc` — نه فقط تست‌های خودش. |

---

## ۸. تعریف «تمام‌شده» (برای هر گام و کل پلن)

هر گام وقتی تمام است که:
1. مدل/مایگریشن + سرویس + ویو + روت + تست‌های ماتریس دسترسی و اعتبارسنجی، لند شده باشند؛
2. فرانت (کارت + متد سرویس + وایر) لند شده باشد و `tsc` سبز باشد؛
3. کل سوئیت advisory (نه فقط فایل خودش) سبز باشد؛
4. ردیف همین گام در این سند تیک بخورد و اسپک مرتبط در `advisor-mvp.md` به‌روز شود؛
5. یک کامیت تمیز با پیام `feat(advisory): restart step-N — <title>`.

کل پلن وقتی تمام است که: موج ۶ لند شود، smoke دیپلوی (گام ۱۳) سبز شود، و دانش‌آموز+مشاور روی پروداکشن چرخۀ کامل «شناخت ← برنامه ← چکینگ ← آزمون ← ارزیابی ← ماه ← چالش» را ببینند.

---

## ۹. نقشۀ PDF → گام (ردیابی پوشش)

| صفحات PDF | قابلیت | گام |
|---|---|---|
| ص۱ | اطلاعات فردی + کلاس‌ها | گام ۲ |
| ص۲ | مقدمه/فلسفه | — (محتوای آموزشی، خارج از دامنه) |
| ص۳ | ماه در یک نگاه | گام ۸ |
| ص۴ | استراتژی‌های ماه | گام ۸ |
| ص۵ | اطلاعات هفتگی + منبع درس | گام ۳ + گام ۴ (dayNotes) |
| ص۶ | کادر آزمون راهبردی | گام ۵ (exam_date/kind پوشش می‌دهد) |
| ص۷ | جدول برنامه‌ریزی هفتگی | گام ۴ |
| ص۸-۹ | چکینگ روزانه | گام ۱ |
| ص۱۰ | ارزیابی هفتگی تیم مشاوره | گام ۷ |
| ص۱۱ | ارزیابی رابط آموزشی | خارج از دامنه (§۳-۱) — آیتم‌ها در گام ۷ ادغام |
| ص۱۷-۱۸ | ارزیابی پس از آزمون + تحلیل کارنامه | گام ۶ |
| ص۱۹-۲۰، ۳۵-۳۶ | نکات مهم آزمون | گام ۶ (notes) |
| ص۳۷ | چالش ۷ روزه | گام ۹ |
| ص۳۸ | خدمات پشتیبانی + طرح تماس | گام ۱۰ (پشتیبان: خارج از دامنه §۳-۲) |
| ص۳۹-۴۱ | مقالات آموزشی | خارج از دامنه (§۳-۴) |
| ص۴۲ | جدول نمرات ماه | گام ۵ |
| ص۴۳-۴۴ | پاسخ‌برگ | خارج از دامنه (§۳-۳) — ثبت دستی با گام ۵ |




