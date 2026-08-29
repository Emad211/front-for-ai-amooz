# رودمپ «همترازی ریسمان» — فاز R (گزارش‌ها، پنل موسسه، برنامه‌ساز هوشمند، جستجو)

وضعیت: **در اجرا — گام‌های ۱ تا ۴ انجام شد ✅ (موج‌های R1+R2) · گام‌های ۵–۶ باقی** · تاریخ: 2026-08-26 · منبع: لیست فیچرهای رقیب (risman.app) + تحلیل شکاف جلسهٔ همان روز · پیش‌نیازها: `docs/features/advisor-mvp.md` + `docs/features/advisor-restart-plan.md` (اجرا‌شدهٔ کامل)

این سند تنها منبع حقیقت فاز R است. هدف: **هیچ‌یک از برتری‌های اعلام‌شدۀ رقیب باقی نماند**، بدون کپی کورکورانه — هر آیتم با زیرساخت موجود ما ترکیب می‌شود.

---

## ۰. خلاصهٔ اجرایی

پنج تحویل P0:

1. ✅ **گام ۱ — جستجو و پوشه/برچسب دانش‌آموزان** (رستر مشاور) — موج R1
2. ✅ **گام ۲ — موتور گزارش + خروجی اکسل** (گزارش پلنر + دانش‌آموز؛ موتور مشترک) — موج R1
3. ✅ **گام ۳ — پنل موسسه (نسخهٔ نازک)** (ساختار مشاوران، تخصیص، داشبورد زنده، گزارش هر مشاور) — موج R2
4. ✅ **گام ۴ — Impersonation** (ورود مستقیم مدیر به حساب مشاور/دانش‌آموز با AuditLog) — موج R2
5. ✅ **گام ۵+۶ — برنامه‌ساز هوشمند** (متن + پیام صوتی ← پیش‌نویس WeeklyPlan با LLM، فقط Draft) — موج R3 — **P0 کامل شد** ✔

سپس P1 (چت، نمودارهای دانش‌آموز، لیگ سحرگاهی، بودجه‌بندی آزمون) و P2 (white-label، آزمون‌ساز مشاور، والدین) — در §۶ فقط خط‌دومی؛ اجرا پس از P0.

**مزیت راهبردی که حفظ می‌کنیم** (ریسمان نمی‌تواند دنبالش برود): پایپ‌لاین محتوایی (جزوهٔ صوتی/تصویری ← فصل ← کوئیز)، OCR دفترچۀ اسکن‌شده، حلقهٔ ترمیم تطبیقی. برنامه‌ساز هوشمند ما به همین‌ها وصل است — برنامهٔ آنها متن خالی است، برنامهٔ ما به فصل واقعی درس و کوئیز همان مبحث می‌رسد.

---

## ۱. اصول قفل‌شده (تغییرناپذیر)

| # | اصل | جزئیات |
|---|---|---|
| ق۱′ | **اصلاح ق۱ ری‌استارت — تک‌سطحِ مجاز LLM** | لایۀ مدیریتی advisory همچنان صفر LLM. **تنها استثنا: برنامه‌ساز هوشمند (گام ۵/۶)** با قیدهای سخت: خروجی همیشه **DRAFT** و هرگز publish خودکار نمی‌شود؛ خروجی با `structured_llm` (Pydantic + یک دور ترمیم) نه parse دستی؛ هر فراخوانی در `LLMUsageLog` ثبت می‌شود؛ پرامپت در `PROMPTS` با کلید ثابت و تست قرارداد. |
| ق۲ | tenancy فقط از `scope.py` + گارد مرزها | سرویس‌های جدید (`reports, folders, org_overview, ai_planner`) به allowlist `test_import_boundaries.py` + assertion پین اضافه می‌شوند. |
| ق۳ | جهت import | `organizations` هرگز `advisory` را import نمی‌کند؛ اندپوینت‌های سطوح موسسه **داخل advisory** سرو می‌شوند (`views_org.py`) با پرمیشن جدید `IsOrgManager` (در `apps/core/permissions.py`). |
| ق۴ | **دکتورین تست (خواستۀ صریح مالک)** | هر گام: (a) ماتریس دسترسی کامل (مالک/غریبه/نقش اشتباه/بی‌احراز)، (b) تست ریاضیِ تجمیع‌ها با اعداد دقیق، (c) کل سوئیت advisory سبز، (d) `tsc --noEmit`، (e) اسموک زندهٔ لوکال. گام ۲: فایل اکسل با openpyxl **بازخوانی و assert** می‌شود. گام ۴: کلاس تست امنیتی اختصاصی. گام ۵: تست قرارداد با **LLM قلابی** (provider stub) + تست پرامپت + تست زندۀ `benchmark` (skip پیش‌فرض). |
| ق۵ | بدون jdatetime سمت سرور | گزارش‌ها و فیلترهای بازه ISO میلادی؛ جلالی فقط فرانت. |
| ق۶ | 404-نه-403 برای غریبه‌ها؛ 409 تعارض وضعیت | مثل فاز قبل. |
| ق۷ | on_delete: engagement ریشه ⇒ CASCADE؛ مرجع بیرونی ⇒ SET_NULL/PROTECT | پوشه حذف شد ⇒ engagements با folder=NULL. |
| ق۸ | وایر camelCase؛ کد/کامنت انگلیسی؛ کپی فارسی | — |
| ق۹ | **بدون پکیج جدید فرانت**؛ بک‌اند فقط **یک** وابستگی جدید مجاز: `openpyxl` (گام ۲، pure-python) | تغییر requirements.txt فقط در همین گام. |
| ق۱۰ | فرانت: ماژول سرویس جدید برای هر فیچر | `advisory-service.ts` فقط با گام ۱ دست می‌خورد (اکسپورت `requestJson` + متدهای پوشه)؛ گام‌های بعدی ماژول‌های جدا می‌سازند (`advisory-reports.ts`, `advisory-org.ts`, `advisory-ai-planner.ts`) که helper اکسپورت‌شده را import می‌کنند — تا ایجنت‌های موازی به فایل مشترک نخورند. |
| ق۱۱ | ویوهای جدید در ماژول‌های جدید | `views_folders.py`, `views_reports.py`, `views_org.py`, `views_ai_planner.py` — `views.py` و ویوهای موجود رشد نمی‌کنند. |

---

## ۲. وضعیت مبنا (موجود و دست‌نخورده)

- advisory تا مایگریشن `0017`؛ ۵۷۰ تست سبز؛ داشبورد کابین مشاور + ۷ تب بازطراحی‌شده (کامیت‌ها تا `a38caba`).
- `organizations` اپ موجود (عضویت، org_role، سابسکریپشن) — پنل موسسه روی همین سوار می‌شود.
- زیرساخت LLM: `apps/commons/llm_provider.py` (MODE=avalai)، `structured_llm.generate_structured`، `PROMPTS`، `transcription.transcribe_media_bytes` (مسیر صوت تک‌مرتبه‌ای چت).
- `LLMUsageLog` برای هزینه/مصرف (از exam-prep) — گام ۵ همان را ثبت می‌کند.
- فرانت: `advisory-service.ts` با `requestJson` خصوصی (گام ۱ آن را اکسپورت می‌کند)؛ recharts نصب.

---

## ۳. خارج از دامنۀ P0 (صریح)

1. **کلاس آنلاین تصویری** — ساخته نمی‌شود (هزینهٔ WebRTC در برابر ارزش)؛ در P2 فقط embed سرویس ثالث بررسی می‌شود.
2. **والدین** — قفل فازهای قبل؛ طراحی چت/گزارش جای پا باز نگه می‌دارد.
3. **White-label و خروجی برندار** — P2.
4. **آزمون‌ساز دستی مشاور (تستی/تشریحی گروهی)** — P2؛ موتور کوئیز موجود مبناست.
5. **سایت معرفی (وردپرس)** — مارکتینگ، نه محصول.
6. **نمودارهای پیشرفت دانش‌آموز، چت، لیگ سحرگاهی، بودجه‌بندی آزمون** — P1؛ در §۶ خط‌دومی. (گام ۲ زیرساخت داده‌ای همهٔ آنها را می‌سازد.)

---

## ۴. قراردادهای سراسری

### ۴.۱ نقشۀ روت (همه زیر `/api/advisory/` مگر سازمانی)

| الگو | متد | نقش | توضیح |
|---|---|---|---|
| `students/` | GET | مشاور | **گسترش موجود**: `?q=` (نام/تلفن، icontains) + `?folder=<id>`؛ پاسخ += `folders:[{id,name}]` و هر دانش‌آموز += `folderId` |
| `folders/` | GET, POST | مشاور | لیست پوشه‌های خودش / ساخت («نام الزامی، ≤۶۴ نویسه») |
| `folders/<int:folder_id>/` | PATCH, DELETE | مشاور | تغییر نام / حذف (engagements با folder=NULL)؛ غریبه ۴۰۴ |
| `students/<int:pk>/folder/` | PATCH | مشاور | `{folderId: id|null}` — انتقال دانش‌آموز بین پوشه‌ها (null = خروج از پوشه)؛ پیاده‌سازی‌شده در گام ۱ |
| `students/<int:pk>/reports/planner/` | GET | مشاور | `?from=&to=` (ISO، اجباری، to≥from) → JSON گزارش پلنر؛ `&format=xlsx` → فایل |
| `students/<int:pk>/reports/student/` | GET | مشاور | همان قرارداد — گزارش دانش‌آموز (مطالعه/تست/سهم درس/نمرات بازه) |
| `org/overview/` | GET | مدیر موسسه | آمار زندهٔ سازمان (دانش‌آموز فعال، برنامهٔ این هفته، لاگ امروز، میانگین تعهد) |
| `org/advisors/` | GET | مدیر موسسه | مشاوران سازمان + آمار هرکدام (تعداد شاگرد، میانگین تعهد شاگردها، برنامه‌های منتشرشدهٔ بازه) `?from=&to=` |
| `org/engagements/<int:pk>/reassign/` | POST | مدیر موسسه | `{advisorId}` — جابجایی دانش‌آموز به مشاور دیگر (هر دو باید هم‌سازمان/هم‌حالت freelanceِ همان سازمان باشند) |
| `plans/ai-draft/` | POST | مشاور | گام ۵: JSON `{prompt: str ≤2000}` · گام ۶: multipart (`voice=true` + `audio` ≤۵MB) → transcription → همان مسیر. هر دو ⇒ 201 پیش‌نویس DRAFT هفتۀ شنبه‌محور: `students/<int:pk>/plans/ai-draft/` |

پرمیشن‌ها: مشاور-روت‌ها `IsAdvisorUser`؛ org-روت‌ها `IsOrgManager` (جدید: کاربر MANAGER + عضویت ACTIVE در حداقل یک سازمان — و scope همیشه به همان سازمان محدود). `extend_schema` روی همه.

### ۴.۲ قواعد وایر
camelCase · تاریخ ISO · خطاها `{"detail": "<فارسی>"}` · PUT/POST set-replace یا صریح · لیست‌ها نزولی تاریخ. اکسل: `Content-Disposition: attachment; filename=report-<kind>-<from>_<to>.xlsx`.

### ۴.۳ مایگریشن‌ها
`advisory.0018_student_folders` (گام ۱) · `organizations.0012_impersonationlog` (گام ۴ — اپ organizations تا 0011 رشد کرده بود) · بقیه گام‌ها بدون مایگریشن (تجمعی/LLM).

### ۴.۴ ماژول‌های جدید (allowlist مرزها به‌روز شود)
بک: `services/folders.py`, `services/reports.py`, `services/excel_export.py`, `services/org_overview.py`, `services/ai_planner.py`, `views_folders.py`, `views_reports.py`, `views_org.py`, `views_ai_planner.py` · فرانت: `services/advisory-reports.ts`, `services/advisory-org.ts`, `services/advisory-ai-planner.ts`, `components/advisory/reports/*`, `app/(manager)/manager/page.tsx`.

---

## ۵. گام‌ها

### گام ۱ — جستجو و پوشه/برچسب دانش‌آموزان · حجم: S/M

**بک‌اند:**
- مایگریشن `0018_student_folders`: مدل `AdvisoryStudentFolder` (advisor FK CASCADE related_name='advisory_folders'، name CharField(64)، created_at؛ UniqueConstraint(advisor, name)) + `AdvisoryEngagement.folder` FK(AdvisoryStudentFolder, SET_NULL, null=True, blank=True, related_name='engagements').
- `services/folders.py`: list/create/rename/delete (حذف ⇒ engagements.folder=NULL در همان تراکنش)؛ مالکیت مطلق مشاور — پوشۀ دیگری ۴۰۴.
- `views_folders.py` + روت‌های §۴.۱؛ گسترش `AdvisorStudentListView`: `?q` (icontains روی first_name+last_name+username+phone)، `?folder`، پاسخ += `folders` (نام/شناسه) و `folderId` هر ردیف.
- **تست:** جستجو روی نام فارسی/تلفن، فیلتر ترکیبی، CRUD پوشه + ماتریس (غریبه ۴۰۴، دانش‌آموز ۴۰۳)، حذف ⇒ NULL، نام تکراری ⇒ 400 «پوشه‌ای با این نام دارید.»، نام خالی/بلند ⇒ 400.

**فرانت (صفحۀ `advisor/students/page.tsx` + `advisory-service.ts`):**
- نوار جستجو با debounce ۳۰۰ms (پارامتر q) + چیپ‌های پوشه (همه / هر پوشه / +پوشۀ جدید) به سبک L5 + منوی هر ردیف برای «انتقال به پوشه».
- `requestJson` از `advisory-service.ts` **اکسپورت** می‌شود (ق۱۰) + متدهای پوشه.
- **تست فرانت:** فقط `tsc`؛ رفتار debounce دستی.

**پذیرش:** مشاور با ~۱۰ دانش‌آموز در <۱ ثانیه به هرکسی برسد؛ پوشه‌بندی و انتقال بدون رفرش صفحه.

---

### گام ۲ — موتور گزارش + خروجی اکسل · حجم: L

**بک‌اند:**
- `requirements.txt` += `openpyxl` (تنها وابستگی جدید فاز).
- `services/reports.py` (توابع خالص، صفر LLM):
  - `planner_report(engagement, date_from, date_to)` → `{days:[{date, planned, actual}], subjects:[{subjectId, name, planned, actual, coveragePercent}], totals:{planned, actual, coveragePercent}}` — planned از آیتم‌های PUBLISHED منقضی‌شده در بازه (کلمپ به today مثل فید)، actual از DailyLogItem همان بازه (کلمپ log به بازه).
  - `student_report(engagement, date_from, date_to)` → `{studySeries:[{date, minutes}], testSeries:[{date, testsTaken}], subjectShare:[{subjectId, name, minutes, sharePercent}], examScores:[ExamScoreItem]}` — از DailyLog/DailyLogItem/tests_taken/StudyExamScore.
  - `advisor_report(advisor, date_from, date_to)` → per-student aggregates + شمارندگان ابزار (plans published, assessments, analyses در بازه) — مصرف گام ۳.
- `services/excel_export.py`: openpyxl — یک شیت per-section، هدر استایل‌دار، `sheet_view.rightToLeft=True`، ستون‌های عرض مناسب؛ خروجی BytesIO.
- `views_reports.py` + روت‌ها: JSON و `format=xlsx` (FileResponse با filename §۴.۲). اعتبارسنجی بازه: اجباری، to≥from، حداکثر طول بازه ۹۲ روز ⇒ 400 «بازه حداکثر ۹۲ روز است.»
- **تست (دکتورین ق۴):** ریاضی دقیق (planned/actual/coverage با اعداد دست‌ساز؛ کلمپ امروز)، بازهٔ خالی ⇒ صفرهای معتبر نه خطا، بازهٔ معکوس/بلند ⇒ 400 فارسی، **xlsx بازخوانی می‌شود و سلول‌های کلیدی assert**، ماتریس دسترسی کامل، غریبه ۴۰۴.

**فرانت:**
- `services/advisory-reports.ts` (import `requestJson` اکسپورت‌شده) + `components/advisory/reports/planner-report-card.tsx`: بازه‌انتخاب (پیش‌فرض ۷ روز اخیر + chips ۷/۱۴/۳۰)، جدول subjects (planned/actual/coverage رنگی)، نمودار میله‌ای plan-vs-actual (recharts، موجود)، دکمۀ «خروجی اکسل» (fetch blob با Authorization → object-URL download).
- mount در تب «گزارش» زیر StudyFeedCard در `students/[id]/page.tsx` (مالکیت این فایل با گام ۲).
- **تست:** `tsc`؛ اسموک دانلود.

**پذیرش:** مشاور بازه بزند → جدول+نمودار+اکسل سالم؛ اعداد با فید/لاگ‌ها می‌خواند.

---

### گام ۳ — پنل موسسه (نسخۀ نازک) · حجم: L

**بک‌اند:**
- `apps/core/permissions.py` += `IsOrgManager` (role=MANAGER + عضویت ACTIVE؛ scope سازمان از عضویت).
- `services/org_overview.py`: `org_overview(org)`, `org_advisor_report(org, from, to)` (مصرف `reports.advisor_report` به‌ازای هر مشاور سازمان + شمارنده‌ها)، `reassign_engagement(engagement, new_advisor, actor)` (هر دو در همان سازمان یا freelance متعلق به سازمان؛ AdvisoryAccessLog-style ردیف ممیزی).
- `views_org.py` + روت‌های §۴.۱. غریبهٔ سازمانی ⇒ ۴۰۴؛ نقش غیرمدیر ⇒ ۴۰۳.
- **تست:** ایزولاسیون سازمان (مدیر A هیچ از B نمی‌بیند)، ریاضی تجمیع، reassign موفق/نامعتبر (مشاور خارج سازمان ⇒ 400 «مشاور انتخابی به این سازمان تعلق ندارد.»)، ماتریس دسترسی.

**فرانت:**
- `services/advisory-org.ts` + صفحۀ جدید `app/(org)/org/advisory/page.tsx` (روتِ `(org)` موجود + گارد نقش در layout + لینک «پنل مشاوره» در `ORG_NAV_MENU`): داشبورد آمار زنده + جدول مشاوران (شاگردها/میانگین تعهد/برنامه‌های بازه + دکمۀ «گزارش اکسل» + ورود مستقیم [گام ۴]) + دیالوگ تخصیص/جابجایی دانش‌آموز.
- **تست:** `tsc`؛ اسموک.

**پذیرش:** مدیر موسسه در یک نگاه وضعیت مشاوران و شاگردهایشان را می‌بیند و دانش‌آموز را جابجا می‌کند.

---

### گام ۴ — Impersonation · حجم: M (امنیت‌محور)

**بک‌اند:**
- `organizations.0012_impersonationlog`: مدل `ImpersonationLog` (manager FK SET_NULL، target_user FK PROTECT، org FK، started_at، ended_at null، ip GenericIPAddress null).
- `POST /api/organizations/<int:org_id>/impersonate/<int:user_id>/` (فقط MANAGER همان سازمان؛ هدف باید عضو همان سازمان باشد — مشاور یا دانش‌آموز): جفت JWT کوتاه‌عمر (access 30min) با claim `imp={by: managerId, org: orgId}` + ردیف Log. `POST .../stop/` ⇒ پایان (ended_at).
- گارد: توکنِ impersonated **نمی‌تواند** دوباره impersonate کند یا اندپوینت‌های org را صدا بزند (چک claim در `IsOrgManager`).
- **تست (کلاس امنیتی اختصاصی):** غیرمدیر ۴۰۳ · مدیر سازمان دیگر ۴۰۴ · هدف خارج سازمان ۴۰۰ · TTL کوتاه (assert claim) · ردیف Log نوشته شد · توکن imp مسدود از org-روت‌ها · stop ثبت می‌شود.

**فرانت:**
- دکمۀ «ورود مستقیم» در جدول مشاوران (گام ۳) + نوار ثابت بالای صفحه هنگام impersonate: «در حال مشاهده به‌عنوان <نام> — خروج» (خروج ⇒ حذف توکن، بازگشت توکن مدیر).

**پذیرش:** مدیر می‌تواند وارد پنل مشاور/دانش‌آموز شود، همه‌چیز را ببیند، و مسیرش در Log است — بدون هیچ راه دورزنی.

---

### گام ۵ — برنامه‌ساز هوشمند (متن) · حجم: L — **تک‌استثنای ق۱′** — ✅ اجرا شد (موج R3)

**بک‌اند:**
- پرامپت `PROMPTS['ai_plan_draft']`: ورودی = پرامپت آزاد مشاور + فهرست `subjects:[{id, name}]` انتخابی دانش‌آموز + تاریخ امروز/شنبۀ هفته؛ خروجی JSON اجباری: `{items:[{dayOffset:0..6, subjectId, plannedMinutes:15..480, topic?:str≤200}]}` — قید: فقط از subjectIds فهرست، جمع دقیقه ≤ ۳۶۰۰.
- `services/ai_planner.py`: `draft_plan_from_text(engagement, prompt, actor)` → `generate_structured(schema=AiPlanDraft, …)` → resolve (subjectId خارج فهرست ⇒ 400 «درس خواسته‌شده در درس‌های دانش‌آموز نیست.») → `study_plans.save_draft(...)` (همۀ قیود پلنر خودبه‌خود اعمال) → بازگشت Draft. ثبت `LLMUsageLog`. خطای provider ⇒ 502 با «سرویس هوش مصنوعی در دسترس نیست.»
- `views_ai_planner.py` + روت `students/<int:pk>/plans/ai-draft/`. **هرگز publish نمی‌کند.**
- **تست:** ProviderStub (JSON آمادهٔ معتبر/نامعتبر): قرارداد schema، ترمیم، resolve خطای درس، Draft واقعاً ساخته شد (و PUBLISHED نشد)، usage-log ثبت، ماتریس دسترسی، پرامپت خالی/>۲۰۰۰ ⇒ 400. تست پرامپت (کلید/placeholderها). `@pytest.mark.benchmark` زنده — skip پیش‌فرض.

**فرانت (اجرا شده):** متدهای `AdvisoryService.draftAiPlan` / `draftAiPlanFromVoice` (با `requestMultipart` هم‌سمنتیک requestJson) + در تب «برنامه» کارت جمع‌شوندهٔ «ساخت پیش‌نویس با هوش مصنوعی» (textarea ≤۲۰۰۰ + دکمۀ میکروفون MediaRecorder) → پس از موفقیت، ادیتور پلنر مستقیماً با ردیف‌های Draft تازه پر می‌شود (مشاور ویرایش/انتشار می‌کند — مسیر موجود).

**پذیرش:** «زهرا این هفته روزی ۲ ساعت ریاضی و جمعه آزمون جامع» → Draft معتبر قابل‌ویرایش در <۱۵ ثانیه؛ هیچ‌وقت چیزی منتشر نمی‌شود که مشاور ندیده.

---

### گام ۶ — برنامه‌ساز صوتی · حجم: S (پس از گام ۵) — ✅ اجرا شد (موج R3)

- همان endpoint با `voice=true` multipart: `transcribe_media_bytes` (موجود) → متن → مسیر گام ۵. سقف **۵MB** ⇒ 400؛ ترنسکریپشن خالی/بی‌صدا ⇒ 400 «صدای ارسالی قابل تشخیص نبود. لطفاً واضح‌تر و نزدیک میکروفون صحبت کنید.»؛ خطای transcription ⇒ 502 «سرویس تبدیل گفتار به متن در دسترس نیست.»
- فرانت: دکمۀ میکروفون کنار textarea (MediaRecorder، ضبط/توقف) — در همان کارت جمع‌شونده.
- **تست:** فایل بزرگ/طولانی ⇒ 400؛ مسیر متنِ حاصل با stub تست می‌شود (transcription هم stub).

---

## ۶. موج‌ها (اجرای موازی با ایجنت‌ها)

| موج | گام‌ها | نکتۀ تعارض |
|---|---|---|
| **R1** | گام ۱ ∥ گام ۲ | فایل‌ها disjoint (A: folders+roster+advisory-service.ts — B: reports+excel+advisory-reports.ts+mount در [id]/page.tsx) |
| **R2** | گام ۳ ← گام ۴ | یک ایجنت، دو فاز (urls.py و نوار فرانت مشترک‌اند) |
| **R3** | گام ۵ ← گام ۶ | یک ایجنت، دو فاز (LLM حساس — تمرکز بالا، پرامپت و تست قرارداد) |
| **P1 (پیش‌نویس)** | چت مشاور-دانش‌آموز · نمودارهای عملکرد (روی reports) · لیگ سحرگاهی · بودجه‌بندی آزمون در MonthlyOutlook | پس از P0، سند جدا |
| **P2 (پیش‌نویس)** | white-label + خروجی برندار · آزمون‌ساز مشاور · embed کلاس آنلاین · والدین | — |

## ۷. ریسک‌ها

| ریسک | پالایش |
|---|---|
| LLM درس/عدد اشتباه بسازد | فقط Draft + resolve سخت‌گیرانه روی subjectIds + باند دقیقه + مرور اجباری مشاور + usage-log |
| هزینه/سوءاستفاده از AI planner | سقف طول پرامپت، یک درخواست در هر تولید، LLMUsageLog قابل‌رسیدگی |
| Impersonation سوءاستفاده | TTL ۳۰ دقیقه، مسدودسازی توکن imp از روت‌های مدیریتی، ImpersonationLog، تست امنیتی اختصاصی |
| openpyxl وابستگی جدید | pure-python؛ تست بازخوانی فایل |
| تعارض ایجنت‌های موازی | ق۱۰: هر فیچر ماژول سرویس فرانت خودش؛ مالکیت فایل در پرامپت هر موج پین می‌شود |
| رگرسیون ۴۰۵/اسلش | هر روت جدید فرانت با trailing slash — review اجباری |

## ۸. تعریف «تمام‌شده» (هر گام و کل فاز)

هر گام: مدل/مایگریشن + سرویس + ویو + روت + ماتریس تست ق۴ + فرانت + `tsc` + کل سوئیت advisory سبز + اسموک زندهٔ لوکال + ردیف همین سند تیک بخورد + کامیت `feat(advisory): risman step-N — <title>`. کل فاز: هر پنج تحویل روی پروداکشن (main) + یادداشت ریلیز `docs/releases/` + گزارش نهایی به مالک.


