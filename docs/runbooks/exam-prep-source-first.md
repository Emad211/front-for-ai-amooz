# Exam Prep source-first OCR4 runbook

این مسیر برای PDF خصوصی آزمون طراحی شده است. فایل PDF و پاسخ خام OCR به AvalAI
ارسال می‌شوند؛ خروجی را خارج از repository و با دسترسی محدود نگه دارید.

## قرارداد تصمیمی

- PDF اصلی و cropهای رندرشده مرجع هستند.
- `mistral-ocr-4-0` فقط متن/هندسه/نشانه‌های visual را به‌عنوان evidence مشتق‌شده
  می‌دهد. confidence به‌تنهایی معیار صحت نیست.
- این command هیچ Gemini/GPT verifierای اجرا نمی‌کند و هیچ رکورد public یا
  `exam_prep_json` را تغییر نمی‌دهد.
- مسیر پیش‌فرض فعلی محصول (`EXAM_PREP_SIMPLE_PIPELINE_ENABLED=True`) با این
  command عوض نمی‌شود. برای rollout کنترل‌شدهٔ مسیر جدید باید هر دو پرچم زیر
  در worker و web یکسان تنظیم شوند؛ کد به‌صورت پیش‌فرض آن‌ها را تغییر نمی‌دهد:

  ```dotenv
  EXAM_PREP_SIMPLE_PIPELINE_ENABLED=False
  EXAM_PREP_V4_ENABLED=True
  EXAM_PREP_V4_SOURCE_FIRST_ENABLED=True
  ```

  در این حالت همان Source Map و بازبینی معلم حفظ می‌شود، OCR4 فقط geometry
  مشتق‌شده می‌دهد، و متن/فرمول semantic همچنان از provider ساختاریافته می‌آید.
  تصویرهای سؤال و راه‌حل از cropهای private صفحهٔ اصلی در endpoint محافظت‌شده
  ساخته می‌شوند؛ راه‌حل برای دانش‌آموز فقط پس از finalized شدن attempt باز می‌شود.
  rollback با برگرداندن دو پرچم اول/سوم به `True`/`False` انجام می‌شود.
- سقف پیش‌فرض هر درخواست ۳۰ صفحه و ۲۸ MiB است. PDFهای ۵۵ و ۵۸ صفحه‌ای معمولاً
  به دو درخواست تقسیم می‌شوند؛ هزینهٔ پایهٔ OCR در نرخ مستند route حدود
  `0.004 × page_count` واحد است (`0.220` و `0.232` واحد، پیش از retry).
- retry پیش‌فرض صفر است (`--max-attempts 1`) تا خطای transient باعث هزینهٔ تکراری
  نشود. پس از بررسی failure می‌توان همان output را با `--resume` و حداکثر یک
  attempt اضافه ادامه داد.
- `EXAM_PREP_SOURCE_FIRST_WORD_CONFIDENCE=1` فقط برای مشاهدهٔ سیگنال confidence است؛
  confidence معیار correctness نیست. برای پاسخ کوچک‌تر می‌توان آن را `0` کرد،
  بدون اینکه متن یا crop مرجع عوض شود.

## پیش‌نیاز

در checkout شاخه‌ای که command روی آن است:

```bash
cd /path/to/front-for-ai-amooz
python -m pip install -r backend/requirements.txt
```

`AVALAI_API_KEY` را فقط در shell خصوصی تنظیم کنید. `AVALAI_BASE_URL` برای این
endpoint لازم نیست؛ OCR4 از `https://api.avalai.ir/v1/ocr` استفاده می‌کند و با
`AVALAI_OCR_ENDPOINT` قابل override است.

## preflight بدون هزینه

```bash
python backend/manage.py extract_exam_prep_source_first \
  --pdf "/private/12T-Kanoon-Jame-20Tir1404-[konkur.in].pdf" \
  --output-dir "/private/source-first/t1404-plan" \
  --dry-run
```

باید `chunkPageCounts` برابر `[30, 25]` و `plannedCostUnitUpperBound` برابر
`0.220` باشد. اگر بیشتر از دو chunk شد، قبل از ارسال علت اندازهٔ chunk را بررسی
کنید؛ آن اجرا دیگر آزمون دو-درخواستی استاندارد نیست.

## دو اجرای آنلاین کم‌هزینه

هر PDF را فقط یک بار اجرا کنید. برای resume، همان output directory را نگه دارید؛
directory جدید نسازید.

```bash
set -euo pipefail
umask 077
ROOT="/path/to/front-for-ai-amooz"
PDF_A="/private/12T-Kanoon-Jame-20Tir1404-[konkur.in].pdf"
PDF_B="/private/12R-Kanoon-16Mordad1405-Jame-[konkur.in].pdf"
OUT="/private/source-first"
mkdir -p "$OUT"

export AVALAI_API_KEY='YOUR_KEY'

python "$ROOT/backend/manage.py" extract_exam_prep_source_first \
  --pdf "$PDF_A" \
  --output-dir "$OUT/t1404" \
  --model mistral-ocr-4-0 \
  --max-pages-per-request 30 \
  --max-chunk-bytes 29360128 \
  --max-response-bytes 125829120 \
  --timeout-seconds 600 \
  --max-attempts 1 \
  --max-planned-cost-unit 0.30 \
  --render-dpi 200 \
  --archive \
  --allow-private-transmission

python "$ROOT/backend/manage.py" extract_exam_prep_source_first \
  --pdf "$PDF_B" \
  --output-dir "$OUT/mordad1405" \
  --model mistral-ocr-4-0 \
  --max-pages-per-request 30 \
  --max-chunk-bytes 29360128 \
  --max-response-bytes 125829120 \
  --timeout-seconds 600 \
  --max-attempts 1 \
  --max-planned-cost-unit 0.30 \
  --render-dpi 200 \
  --archive \
  --allow-private-transmission
```

پس از هر اجرا فقط `manifest.safe.json` را برای گزارش اولیه بخوانید. برای تصمیم
دقت، `manifest.json` و `analysis.json` خصوصی‌اند و باید نزد مالک PDF بمانند.

```bash
python - "$OUT/t1404/manifest.safe.json" "$OUT/mordad1405/manifest.safe.json" <<'PY'
import json, sys
for name in sys.argv[1:]:
    m = json.load(open(name, encoding='utf-8'))
    assert m['allPhysicalPagesReturned'] is True
    expected = [min(30, m['pageCount'])]
    if m['pageCount'] > 30:
        expected.append(m['pageCount'] - 30)
    assert m['chunkPageCounts'] == expected
    assert m['acceptancePassed'] is True
    assert m['retryCount'] == 0
    print(name, json.dumps({
        k: m[k] for k in ('pageCount','chunkCount','chunkPageCounts',
                           'questionRegions','solutionRegions','itemCount',
                           'itemsNeedingHumanReview','estimatedCostUnit')
    }, ensure_ascii=False))
PY
```

برای PDF دوم ۵۸ صفحه‌ای، chunkهای درست `[30, 28]` هستند. اگر تعداد صفحات فایل
واقعاً ۵۵ است ولی خروجی دیگری دیدید، اجرای آنلاین را متوقف کنید.

## resume پس از خطای transient

اگر command در chunk دوم متوقف شد، chunk اول را دوباره پولی نکنید:

```bash
python backend/manage.py extract_exam_prep_source_first \
  --pdf "/private/12T-Kanoon-Jame-20Tir1404-[konkur.in].pdf" \
  --output-dir "/private/source-first/t1404" \
  --model mistral-ocr-4-0 \
  --max-pages-per-request 30 \
  --max-chunk-bytes 29360128 \
  --max-response-bytes 125829120 \
  --timeout-seconds 600 \
  --max-attempts 2 \
  --max-planned-cost-unit 0.50 \
  --resume \
  --allow-private-transmission
```

`checkpoint.json` فقط وقتی chunk را reuse می‌کند که hash، page coverage و response
ساختاری معتبر باشند. خطاهای 400/401/403/404/422 یا `model_access_limited` را
resume نکنید تا تنظیمات key/model اصلاح شود.

## تفسیر خروجی

- `items/*.source.jpg` و PDF اصلی authoritative هستند.
- `items[*].ocrText` برای search/index/کمک به AI است، نه متن قابل انتشار بدون
  بازبینی.
- `qualityFlags`، `visualRequired` و `needsHumanReview` صف selective review را
  می‌سازند؛ مورد سالم با confidence بالا هم تضمین correctness نیست.
- `manifest.safe.json` برای مقایسهٔ هزینه/coverage است و متن سؤال ندارد.

فعلاً verifier چندمدلی را به‌صورت پیش‌فرض فعال نکنید. بعد از دیدن دو manifest و
نمونهٔ cropهای flagged، فقط اگر خطای واقعی تکرارشونده باشد یک verifier تک‌تصویر
و target-only اضافه می‌شود؛ این مرحلهٔ دوم است و سقف هزینهٔ جداگانه خواهد داشت.
