/**
 * =============================================================================
 * LANDING PAGE MOCK DATA - داده‌های آزمایشی صفحه فرود
 * =============================================================================
 */

export const MOCK_TESTIMONIALS = [
  {
    name: "آرش راد",
    role: "دانش‌آموز پایه دوازدهم • رتبه ۱۲۳ کنکور",
    content: "با AI-Amooz تونستم مفاهیم پیچیده ریاضی رو به سادگی یاد بگیرم. دستیار هوشمندش همیشه برای رفع اشکال کنارم بود و باعث شد با اعتماد به نفس بیشتری برای کنکور آماده بشم.",
    image: "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?q=80&w=200&h=200&auto=format&fit=crop"
  },
  {
    name: "ثنا جاوید",
    role: "دانش‌آموز پایه یازدهم تجربی",
    content: "مسیر یادگیری شخصی‌سازی شده واقعاً به من کمک کرد تا روی نقاط ضعفم تمرکز کنم. قبلاً ساعت‌ها وقتم رو برای پیدا کردن منابع هدر می‌دادم، اما الان همه چیز آماده‌ست.",
    image: "https://images.unsplash.com/photo-1494790108377-be9c29b29330?q=80&w=200&h=200&auto=format&fit=crop"
  },
  {
    name: "بردیا نیک‌بین",
    role: "دانش‌آموز پایه دهم ریاضی",
    content: "آزمون‌های تطبیقی فوق‌العاده هستن. هر بار که اشتباه می‌کنم، هوش مصنوعی دقیقاً همون مبحث رو دوباره با مثال‌های ساده‌تر برام توضیح میده تا کاملاً یاد بگیرم.",
    image: "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?q=80&w=200&h=200&auto=format&fit=crop"
  }
];

export const MOCK_FAQS = [
  {
    id: "item-1",
    question: "AI-Amooz برای چه مقاطع و درس‌هایی مناسب است؟",
    answer: "در حال حاضر روی دروس تخصصی متوسطه دوم (ریاضیات، فیزیک و علوم کامپیوتر) متمرکز هستیم. به طور مداوم در حال گسترش محتوا برای رشته‌ها و مقاطع بیشتر هستیم."
  },
  {
    id: "item-2",
    question: "آیا استفاده از دستیار هوشمند رایگان است؟",
    answer: "بله! ثبت‌نام و استفاده از بخش قابل توجهی از امکانات رایگان است. برای دسترسی نامحدود، پلن‌های اشتراک مقرون‌به‌صرفه داریم."
  },
  {
    id: "item-3",
    question: "چگونه مسیر یادگیری شخصی‌سازی می‌شود؟",
    answer: "با یک آزمون تعیین سطح اولیه، نقاط قوت و ضعف شما شناسایی می‌شود. سپس با تحلیل مداوم عملکرد، نقشه راه به‌روزرسانی می‌شود."
  },
  {
    id: "item-4",
    question: "آیا می‌توانم از موبایل استفاده کنم؟",
    answer: "بله! پلتفرم کاملاً ریسپانسیو است و می‌توانید از هر دستگاهی استفاده کنید. اپلیکیشن موبایل هم به زودی منتشر می‌شود."
  }
];

export const MOCK_FEATURES = [
  {
    id: 1,
    title: "مسیر یادگیری شخصی",
    description: "هوش مصنوعی سطح دانش شما را می‌سنجد و بهترین مسیر آموزشی را برای رسیدن به اهداف‌تان طراحی می‌کند.",
    icon: "Target",
    large: true
  },
  {
    id: 2,
    title: "یادگیری سریع",
    description: "با متدهای هوشمند، سریع‌تر یاد بگیرید.",
    icon: "Zap",
    large: false
  },
  {
    id: 3,
    title: "تحلیل پیشرفت",
    description: "نقاط ضعف و قوت خود را بشناسید.",
    icon: "Brain",
    large: false
  },
  {
    id: 4,
    title: "دستیار هوشمند ۲۴/۷",
    description: "در هر لحظه سوالات درسی بپرسید، راه‌حل‌های مختلف را بررسی کنید و اشکالات خود را رفع کنید.",
    icon: "Bot",
    large: true
  },
  {
    id: 5,
    title: "آزمون‌های تطبیقی",
    description: "آزمون‌هایی که بر اساس نقاط ضعف و قوت شما طراحی می‌شوند.",
    icon: "BookCheck",
    large: false
  },
  {
    id: 6,
    title: "تحلیل پیشرفت",
    description: "نقاط ضعف و قوت خود را بشناسید و بهبود دهید.",
    icon: "BarChart3",
    large: false
  }
];

export const MOCK_STEPS = [
  {
    id: 1,
    number: "۱",
    title: "ثبت‌نام و تعیین هدف",
    description: "به ما بگویید در چه درسی و برای چه هدفی به کمک نیاز دارید. کنکور، امتحان نهایی یا تقویت پایه.",
    mobileDescription: "به ما بگویید در چه درسی و برای چه هدفی به کمک نیاز دارید."
  },
  {
    id: 2,
    number: "۲",
    title: "دریافت نقشه راه",
    description: "هوش مصنوعی یک مسیر یادگیری مخصوص شما شامل درسنامه، تمرین و آزمون ایجاد می‌کند.",
    mobileDescription: "هوش مصنوعی یک مسیر یادگیری مخصوص شما ایجاد می‌کند."
  },
  {
    id: 3,
    number: "۳",
    title: "شروع یادگیری",
    description: "با همراهی دستیار هوشمند مراحل را طی کنید و پیشرفت خود را لحظه به لحظه ببینید.",
    mobileDescription: "با همراهی دستیار هوشمند مراحل را طی کنید و پیشرفت خود را ببینید."
  }
];

export const MOCK_PLACEHOLDER_IMAGES = [
  {
    id: "landing-hero",
    description: "A futuristic image representing AI-powered learning and data visualization.",
    imageUrl: "https://images.unsplash.com/photo-1745674684639-9cef0092212c?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3NDE5ODJ8MHwxfHNlYXJjaHw1fHxBSSUyMGxlYXJuaW5nfGVufDB8fHx8MTc2NjcwNzQ5M3ww&ixlib=rb-4.1.0&q=80&w=1080",
    imageHint: "AI learning"
  },
  {
    id: "testimonial-avatar",
    description: "Avatar for a student testimonial.",
    imageUrl: "https://images.unsplash.com/photo-1529068755536-a5ade0dcb4e8?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3NDE5ODJ8MHwxfHNlYXJjaHwxfHxzdHVkZW50JTIwcG9ydHJhaXR8ZW58MHx8fHwxNzY2NjQ0ODAwfDA&ixlib=rb-4.1.0&q=80&w=1080",
    imageHint: "student portrait"
  }
];
