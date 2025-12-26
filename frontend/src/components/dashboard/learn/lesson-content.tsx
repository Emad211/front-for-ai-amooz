'use client';

import { BarChart, Signal, Clock, PlayCircle } from 'lucide-react';

export const LessonContent = () => (
  <section className="flex-1 flex flex-col gap-3 overflow-y-auto no-scrollbar h-full rounded-2xl relative">
    <div className="bg-card border border-border rounded-2xl p-4 shadow-lg relative overflow-hidden flex-shrink-0">
      <div className="flex flex-col gap-4">
        <div>
          <h1 className="text-lg font-bold text-foreground mb-1">رسم نمودار توابع درجه دوم (سهمی)</h1>
          <p className="text-sm text-muted-foreground leading-relaxed line-clamp-1">
            یادگیری چگونگی رسم دقیق نمودارهای توابع درجه دوم (سهمی) و تفسیر ویژگی‌های کلیدی آن‌ها.
          </p>
        </div>
        <div className="flex items-center justify-between text-sm text-muted-foreground border-t border-border pt-3">
          <div className="flex items-center gap-2">
            <BarChart className="h-4 w-4 text-primary" />
            <span>
              تکمیل: <span className="font-bold text-foreground">۶۷٪</span>
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Signal className="h-4 w-4 text-primary" />
            <span>
              سطح: <span className="font-bold text-foreground">مبتدی</span>
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Clock className="h-4 w-4 text-primary" />
            <span>
              زمان: <span className="font-bold text-foreground">۳۰-۴۵ دقیقه</span>
            </span>
          </div>
        </div>
      </div>
    </div>
    <div className="bg-card border border-border rounded-2xl p-6 sm:p-8 flex-1 shadow-xl overflow-y-auto no-scrollbar">
      <div className="flex items-center gap-3 mb-6 pb-3 border-b border-border/50">
        <div className="h-8 w-8 rounded-lg bg-primary/10 flex items-center justify-center text-primary">
          <PlayCircle className="h-5 w-5" />
        </div>
        <h2 className="text-lg font-bold text-foreground">رأس سهمی: مهمترین نقطه</h2>
      </div>
      <div className="prose prose-invert max-w-none text-muted-foreground leading-relaxed space-y-6">
        <p className="text-justify">
          رأس سهمی (Vertex) نقطه‌ای است که در آن سهمی تغییر جهت می‌دهد. این نقطه در واقع بحرانی‌ترین بخش یک سهمی است، زیرا تعیین‌کننده مقدار مینیمم یا ماکزیمم تابع درجه دوم می‌باشد.
        </p>

        <div className="bg-card/50 border border-border/50 rounded-xl p-6 my-6">
          <h3 className="text-foreground font-bold mb-4 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-primary"></span>
            فرمول‌های کلیدی
          </h3>
          <div className="space-y-4">
            <div className="flex items-center justify-between bg-background/50 p-3 rounded-lg border border-border/30">
              <span>طول رأس سهمی (x)</span>
              <code className="text-primary font-mono text-lg" dir="ltr">x = -b / 2a</code>
            </div>
            <div className="flex items-center justify-between bg-background/50 p-3 rounded-lg border border-border/30">
              <span>عرض رأس سهمی (y)</span>
              <code className="text-primary font-mono text-lg" dir="ltr">y = f(-b / 2a)</code>
            </div>
          </div>
        </div>

        <h3 className="text-foreground font-bold mt-8 mb-4">ویژگی‌های مهم رأس سهمی:</h3>
        <ul className="list-disc list-inside space-y-3 pr-4">
          <li>اگر <code className="text-primary" dir="ltr">a &gt; 0</code> باشد، دهانه سهمی رو به بالاست و رأس سهمی نقطه <strong>مینیمم</strong> است.</li>
          <li>اگر <code className="text-primary" dir="ltr">a &lt; 0</code> باشد، دهانه سهمی رو به پایین است و رأس سهمی نقطه <strong>ماکزیمم</strong> است.</li>
          <li>خط تقارن سهمی همواره یک خط عمودی است که از رأس سهمی می‌گذرد (<code className="text-primary" dir="ltr">x = -b/2a</code>).</li>
        </ul>

        <div className="mt-8 p-4 bg-primary/5 border-r-4 border-primary rounded-l-lg italic">
          نکته کنکوری: در مسائل بهینه‌سازی، هرگاه صحبت از بیشترین یا کمترین مقدار یک تابع درجه دوم باشد، هدف یافتن عرض رأس سهمی است.
        </div>
      </div>
    </div>
  </section>
);
