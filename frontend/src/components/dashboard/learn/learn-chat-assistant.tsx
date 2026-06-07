'use client';

import React from 'react';
import { Bot, PanelRightClose, Send, Paperclip, Mic, X, ChevronLeft, ChevronRight, AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import { SheetClose } from '@/components/ui/sheet';
import { MarkdownWithMath } from '@/components/content/markdown-with-math';
import { DashboardService } from '@/services/dashboard-service';
import { normalizeMathText } from '@/lib/normalize-math-text';
import {
  InteractiveFlashcard,
  InteractiveMatchGame,
  InteractiveQuiz,
  InteractiveScenario,
  InteractiveNotes,
} from './widgets';

interface ChatMessageProps {
  sender: 'ai' | 'user';
  time: string;
  message: string;
  widget?: { widget_type: string; data: any } | null;
}

function formatTime(d: Date): string {
  const hh = d.getHours().toString().padStart(2, '0');
  const mm = d.getMinutes().toString().padStart(2, '0');
  return `${hh}:${mm}`;
}

function formatDuration(totalSeconds: number): string {
  const secs = Math.max(0, Math.floor(totalSeconds || 0));
  const mm = Math.floor(secs / 60).toString().padStart(2, '0');
  const ss = (secs % 60).toString().padStart(2, '0');
  return `${mm}:${ss}`;
}

function WidgetCard({ widgetType, data }: { widgetType: string; data: any }) {
  const type = String(widgetType || '').trim();

  // Helper to find an array in the data object/array
  const findArray = (d: any, keys: string[]): any[] => {
    if (Array.isArray(d)) return d;
    if (!d || typeof d !== 'object') return [];
    for (const key of keys) {
      if (Array.isArray(d[key])) return d[key];
    }
    // Deep fallback: find the first array-like field
    for (const key in d) {
      if (Array.isArray(d[key])) return d[key];
    }
    return [];
  };

  // Interactive widgets
  if (type === 'flashcard') {
    const flashcards = findArray(data, ['flashcards', 'cards', 'result']);
    return (
      <div className="mt-2 rounded-xl border border-border bg-card p-3">
        <InteractiveFlashcard flashcards={flashcards} />
      </div>
    );
  }

  if (type === 'match_game') {
    const pairs = findArray(data, ['pairs', 'matches', 'result']);
    return (
      <div className="mt-2 rounded-xl border border-border bg-card p-3">
        <InteractiveMatchGame pairs={pairs} />
      </div>
    );
  }

  if (type === 'quiz' || type === 'practice_test') {
    const questions = findArray(data, ['questions', 'quiz', 'test_items', 'result']);
    return (
      <div className="mt-2 rounded-xl border border-border bg-card p-3">
        <InteractiveQuiz questions={questions} />
      </div>
    );
  }

  if (type === 'scenario') {
    const scenarios = findArray(data, ['scenarios', 'result']);
    const finalScenarios = scenarios.length ? scenarios : (data?.context || data?.scenario ? [data] : []);
    return (
      <div className="mt-2 rounded-xl border border-border bg-card p-3">
        <InteractiveScenario scenarios={finalScenarios} />
      </div>
    );
  }

  if (type === 'notes') {
    const items = findArray(data, ['items', 'result']);
    const finalItems = items.length ? items : (data?.notes_markdown || data?.summary_markdown ? [data] : []);
    return (
      <div className="mt-2 rounded-xl border border-border bg-card p-3">
        <InteractiveNotes items={finalItems} />
      </div>
    );
  }

  // Fallback for image or unknown types
  if (type === 'image') {
    const images = data?.images || [];
    if (!Array.isArray(images) || images.length === 0) {
      return <div className="text-xs text-muted-foreground mt-2">تصویری موجود نیست.</div>;
    }
    return (
      <div className="mt-2 rounded-xl border border-border bg-card p-3 space-y-2">
        <div className="text-xs font-medium text-muted-foreground">🖼️ ایده‌ی تصویر</div>
        {images.slice(0, 3).map((im: any, idx: number) => (
          <div key={idx} className="rounded-lg bg-background/40 border border-border/50 p-2">
            <div className="text-[11px] text-muted-foreground mb-1">{String(im?.caption ?? '')}</div>
            <div className="text-[10px] font-mono break-words" dir="ltr">{String(im?.prompt ?? '')}</div>
          </div>
        ))}
      </div>
    );
  }

  // Generic fallback
  return (
    <div className="mt-2 rounded-xl border border-border bg-card p-3">
      <div className="text-xs font-medium text-muted-foreground mb-2">ابزار</div>
      <div className="text-xs text-muted-foreground">محتوای ابزار در دسترس نیست.</div>
    </div>
  );
}

export const ChatMessage = ({ sender, time, message, widget }: ChatMessageProps) => {
  const isAI = sender === 'ai';
  return (
    <div className={`flex flex-col gap-1 ${!isAI && 'items-end'}`}>
      <div className={`flex items-start gap-2 ${!isAI && 'flex-row-reverse'}`}>
        {isAI && (
          <div className="h-7 w-7 rounded-full bg-secondary flex-shrink-0 flex items-center justify-center border border-border mt-1">
            <Bot className="text-primary h-4 w-4" />
          </div>
        )}
        <div
          className={cn(
            'p-3 rounded-2xl leading-6 shadow-sm border max-w-[85%] sm:max-w-[90%] break-words',
            isAI ? 'bg-card text-foreground rounded-tr-none border-border/50' : 'bg-primary/10 text-foreground rounded-tl-none border-primary/20'
          )}
        >
          <MarkdownWithMath markdown={normalizeMathText(message)} className="text-sm" />
          {isAI && widget?.widget_type ? <WidgetCard widgetType={widget.widget_type} data={widget.data} /> : null}
        </div>
      </div>
      <span className={`text-[10px] sm:text-[9px] text-muted-foreground ${isAI ? 'pr-11' : 'pl-1'}`}>{time}</span>
    </div>
  );
};

interface ChatAssistantProps {
  onToggle: () => void;
  isOpen: boolean;
  className?: string;
  isMobile?: boolean;
  courseId?: string;
  lessonId?: string | null;
  lessonTitle?: string;
  pageContext?: string;
  pageMaterial?: string;
  studentName?: string;
}

type ChatApiResponse =
  | { type: 'text'; content: string; suggestions?: string[] }
  | { type: 'widget'; widget_type: string; data: any; text?: string; suggestions?: string[] };

type ChatErrorKind = 'timeout' | 'network' | 'auth' | 'rate' | 'server' | 'unknown' | 'mic';

interface ChatErrorInfo {
  kind: ChatErrorKind;
  title: string;
  detail?: string;
}

function getChatErrorInfo(error: unknown, fallbackTitle: string): ChatErrorInfo {
  const raw = error instanceof Error ? error.message : String(error ?? '');
  const msg = raw.trim().toLowerCase();

  if (msg.includes('timeout') || msg.includes('timed out')) {
    return {
      kind: 'timeout',
      title: 'پاسخی از سرور دریافت نشد.',
      detail: 'ارتباط کند یا سرور شلوغ است. چند لحظه بعد دوباره تلاش کن.',
    };
  }
  if (
    msg.includes('ssl') ||
    msg.includes('eof') ||
    msg.includes('connect') ||
    msg.includes('network') ||
    msg.includes('failed to fetch') ||
    msg.includes('cors')
  ) {
    return {
      kind: 'network',
      title: 'ارتباط با سرور ناپایدار بود.',
      detail: 'اینترنت، VPN یا فایروال را بررسی کن و دوباره امتحان کن.',
    };
  }
  if (msg.includes('401') || msg.includes('token') || msg.includes('unauthorized')) {
    return {
      kind: 'auth',
      title: 'برای ادامه باید دوباره وارد شوی.',
      detail: 'نشست شما منقضی شده است.',
    };
  }
  if (msg.includes('429') || msg.includes('rate')) {
    return {
      kind: 'rate',
      title: 'تعداد درخواست‌ها زیاد شد.',
      detail: 'چند ثانیه صبر کن و دوباره تلاش کن.',
    };
  }
  if (msg.includes('500') || msg.includes('server')) {
    return {
      kind: 'server',
      title: 'خطای سرور رخ داد.',
      detail: 'این مشکل معمولاً موقتی است.',
    };
  }
  if (msg.includes('microphone') || msg.includes('mic') || msg.includes('media')) {
    return {
      kind: 'mic',
      title: 'دسترسی به میکروفون انجام نشد.',
      detail: 'اجازه دسترسی را بررسی کن و دوباره امتحان کن.',
    };
  }
  return {
    kind: 'unknown',
    title: fallbackTitle,
    detail: 'اگر مشکل ادامه داشت، یک بار صفحه را تازه‌سازی کن.',
  };
}

export const ChatAssistant = ({ onToggle, isOpen, className, isMobile = false, courseId, lessonId, lessonTitle, pageContext, pageMaterial, studentName }: ChatAssistantProps) => {
  const [message, setMessage] = React.useState('');
  const [messages, setMessages] = React.useState<
    Array<{ id: string; sender: 'ai' | 'user'; time: string; message: string; widget?: { widget_type: string; data: any } | null }>
  >([]);
  const [suggestions, setSuggestions] = React.useState<string[]>([]);
  const [pendingFile, setPendingFile] = React.useState<File | null>(null);
  const [isSending, setIsSending] = React.useState(false);
  const [historyLoaded, setHistoryLoaded] = React.useState(false);
  const [chatError, setChatError] = React.useState<ChatErrorInfo | null>(null);
  const [retryAvailable, setRetryAvailable] = React.useState(false);
  const lastActionRef = React.useRef<null | (() => void)>(null);

  const [isRecording, setIsRecording] = React.useState(false);
  const recorderRef = React.useRef<MediaRecorder | null>(null);
  const recordChunksRef = React.useRef<BlobPart[]>([]);
  const recordStartRef = React.useRef<number | null>(null);
  const [recordSeconds, setRecordSeconds] = React.useState(0);
  const [recordedSeconds, setRecordedSeconds] = React.useState<number | null>(null);

  const textareaRef = React.useRef<HTMLTextAreaElement>(null);
  const scrollRef = React.useRef<HTMLDivElement>(null);
  const fileInputRef = React.useRef<HTMLInputElement>(null);
  const suggestionsRef = React.useRef<HTMLDivElement>(null);

  const clearChatError = React.useCallback(() => {
    setChatError(null);
    setRetryAvailable(false);
    lastActionRef.current = null;
  }, []);

  const setChatErrorWithAction = React.useCallback((error: unknown, action: (() => void) | null, fallbackTitle: string) => {
    setChatError(getChatErrorInfo(error, fallbackTitle));
    lastActionRef.current = action;
    setRetryAvailable(Boolean(action));
  }, []);

  const scrollSuggestions = React.useCallback((direction: 'left' | 'right') => {
    const el = suggestionsRef.current;
    if (!el) return;
    const amount = Math.max(140, Math.floor(el.clientWidth * 0.6));
    const delta = direction === 'left' ? -amount : amount;
    el.scrollBy({ left: delta, behavior: 'smooth' });
  }, []);

  const threadKey = React.useMemo(() => {
    const base = String(courseId ?? '').trim();
    const lid = String(lessonId ?? '').trim();
    const ctx = String(pageContext ?? '').trim();
    return `${base}:${lid || ctx || 'root'}`;
  }, [courseId, lessonId, pageContext]);

  const isProtocolMessage = React.useCallback((text: string) => {
    const msg = String(text ?? '').trim();
    return msg.startsWith('SYSTEM_') || msg.startsWith('ACTIVATION_');
  }, []);

  const handleInputChange = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
    setMessage(event.target.value);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  };

  const scrollToBottom = React.useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    requestAnimationFrame(() => {
      el.scrollTop = el.scrollHeight;
    });
  }, []);

  // Scroll to bottom on open or new messages
  React.useEffect(() => {
    if (!isOpen) return;
    scrollToBottom();
  }, [isOpen, messages.length, scrollToBottom]);

  // Reset chat when lesson/thread changes (legacy behavior: thread_id includes unit).
  React.useEffect(() => {
    setMessages([]);
    setSuggestions([]);
    setPendingFile(null);
    setMessage('');
    setHistoryLoaded(false);
    clearChatError();
  }, [threadKey]);

  // Load persisted history from backend (so student sees previous chat after returning).
  React.useEffect(() => {
    if (!isOpen) return;
    const cid = String(courseId ?? '').trim();
    if (!cid) return;
    if (historyLoaded) return;

    let cancelled = false;

    const run = async () => {
      try {
        const hist = await DashboardService.getCourseChatHistory(cid, lessonId ?? null);
        if (cancelled) return;

        const items = Array.isArray(hist?.items) ? hist.items : [];
        const mapped = items
          .filter((it: any) => {
            const role = String(it?.role ?? '').trim();
            const content = String(it?.content ?? '').trim();
            if (role === 'system') return false;
            if (content.startsWith('SYSTEM_') || content.startsWith('ACTIVATION_')) return false;
            return true;
          })
          .map((it: any) => {
          const role = String(it?.role ?? 'assistant');
          const sender: 'ai' | 'user' = role === 'user' ? 'user' : 'ai';
          const createdAt = it?.created_at ? new Date(String(it.created_at)) : new Date();
          const type = String(it?.type ?? 'text');
          const payload = it?.payload;
          const widget =
            sender === 'ai' && type === 'widget' && payload && payload.widget_type
              ? { widget_type: String(payload.widget_type), data: payload.data }
              : null;

          return {
            id: `hist-${String(it?.id ?? Math.random())}`,
            sender,
            time: formatTime(createdAt),
            message: String(it?.content ?? ''),
            widget,
          };
        });

        setMessages(mapped);

        // Update suggestions based on last assistant message.
        const last = items.length > 0 ? items[items.length - 1] : null;
        const nextSuggestions = Array.isArray(last?.suggestions) ? last.suggestions.filter(Boolean) : [];
        setSuggestions(nextSuggestions);
      } catch (error) {
        setChatErrorWithAction(
          error,
          () => {
            setHistoryLoaded(false);
          },
          'بارگذاری گفتگو ناموفق بود.'
        );
      } finally {
        if (!cancelled) setHistoryLoaded(true);
      }
    };

    run();

    return () => {
      cancelled = true;
    };
  }, [isOpen, courseId, lessonId, threadKey, historyLoaded]);

  // Boot message: fixed local greeting (no activation/unit-start protocol).
  React.useEffect(() => {
    if (!isOpen) return;
    if (!historyLoaded) return;
    if (messages.length > 0) return;
    const now = new Date();
    setMessages([
      {
        id: `${Date.now()}-ai-intro`,
        sender: 'ai',
        time: formatTime(now),
        message: 'سلام! من دستیار یادگیری شما هستم. هر سوالی داری بپرس تا کمک کنم.',
        widget: null,
      },
    ]);
    setSuggestions(['مفهومش رو توضیح بده', 'جزییات بیشتر می‌خواهم', 'مثال درسی بزن']);
  }, [isOpen, historyLoaded, messages.length]);

  React.useEffect(() => {
    if (!isRecording) return;
    const interval = window.setInterval(() => {
      const start = recordStartRef.current;
      if (!start) return;
      const secs = Math.floor((Date.now() - start) / 1000);
      setRecordSeconds(secs);
    }, 500);
    return () => window.clearInterval(interval);
  }, [isRecording]);

  const pushMessage = React.useCallback((m: { sender: 'ai' | 'user'; message: string; widget?: { widget_type: string; data: any } | null }) => {
    setMessages((prev) => [
      ...prev,
      {
        id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
        sender: m.sender,
        time: formatTime(new Date()),
        message: m.message,
        widget: m.widget ?? null,
      },
    ]);
    setTimeout(() => {
      if (scrollRef.current) {
        scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
      }
    }, 50);
  }, []);

  const sendMessage = React.useCallback(
    async (text: string, opts?: { skipUserEcho?: boolean }) => {
      const cid = String(courseId ?? '').trim();
      if (!cid) {
        pushMessage({ sender: 'ai', message: 'شناسه کلاس مشخص نیست.' });
        return;
      }
      const msg = String(text ?? '').trim();
      if (!msg && !pendingFile) return;
      if (isSending) return;

      clearChatError();

      const skipEcho = Boolean(opts?.skipUserEcho);
      if (msg && !skipEcho && !isProtocolMessage(msg)) {
        pushMessage({ sender: 'user', message: msg });
      }

      setIsSending(true);
      try {
        let resp: ChatApiResponse;
        if (pendingFile) {
          const fd = new FormData();
          fd.append('file', pendingFile);
          fd.append('message', msg);
          if (lessonId) fd.append('lesson_id', lessonId);
          if (pageContext) fd.append('page_context', pageContext);
          if (pageMaterial) fd.append('page_material', pageMaterial);
          if (studentName) fd.append('student_name', studentName);
          resp = (await DashboardService.sendCourseChatMedia(cid, fd)) as ChatApiResponse;
        } else {
          resp = (await DashboardService.sendCourseChatMessage(cid, {
            message: msg,
            lesson_id: lessonId ?? null,
            page_context: pageContext ?? '',
            page_material: pageMaterial ?? '',
            student_name: studentName ?? '',
          })) as ChatApiResponse;
        }

        if (resp?.type === 'text') {
          pushMessage({ sender: 'ai', message: String(resp.content ?? '').trim() || '...' });
        } else if (resp?.type === 'widget') {
          const textOut = String(resp.text ?? '').trim();
          pushMessage({ sender: 'ai', message: textOut || 'انجام شد.', widget: { widget_type: resp.widget_type, data: resp.data } });
        } else {
          pushMessage({ sender: 'ai', message: 'پاسخ نامعتبر از سرور دریافت شد.' });
        }

        const nextSuggestions = Array.isArray((resp as any)?.suggestions) ? (resp as any).suggestions.filter(Boolean) : [];
        setSuggestions(nextSuggestions);
        setPendingFile(null);
        // Refresh persisted history so the UI stays in sync with backend storage.
        setHistoryLoaded(false);
      } catch (e) {
        setChatErrorWithAction(
          e,
          () => {
            void sendMessage(text, opts);
          },
          'ارسال پیام ناموفق بود.'
        );
        const msgErr = e instanceof Error ? e.message : 'خطا در ارسال پیام';
        pushMessage({ sender: 'ai', message: msgErr });
        setSuggestions([]);
      } finally {
        setIsSending(false);
      }
    },
    [courseId, isSending, isProtocolMessage, lessonId, pageContext, pageMaterial, pendingFile, pushMessage, studentName, clearChatError, setChatErrorWithAction]
  );

  const toggleRecording = React.useCallback(async () => {
    if (isSending) return;

    if (isRecording) {
      try {
        recorderRef.current?.stop();
      } catch {
        // ignore
      }
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream);
      recorderRef.current = rec;
      recordChunksRef.current = [];
      recordStartRef.current = Date.now();
      setRecordSeconds(0);
      setRecordedSeconds(null);

      rec.ondataavailable = (ev) => {
        if (ev.data && ev.data.size > 0) {
          recordChunksRef.current.push(ev.data);
        }
      };

      rec.onstop = () => {
        setIsRecording(false);
        const chunks = recordChunksRef.current;
        recordChunksRef.current = [];
        const blob = new Blob(chunks, { type: rec.mimeType || 'audio/webm' });
        // Stop tracks.
        stream.getTracks().forEach((t) => t.stop());
        const file = new File([blob], `voice-${Date.now()}.webm`, { type: blob.type || 'audio/webm' });
        setPendingFile(file);
        const duration = recordStartRef.current ? Math.floor((Date.now() - recordStartRef.current) / 1000) : recordSeconds;
        setRecordedSeconds(duration);
      };

      rec.start();
      setIsRecording(true);
    } catch (e) {
      setChatErrorWithAction(e, null, 'دسترسی به میکروفون انجام نشد.');
      const msgErr = e instanceof Error ? e.message : 'خطا در دسترسی به میکروفون';
      pushMessage({ sender: 'ai', message: msgErr });
    }
  }, [isRecording, isSending, pushMessage, setChatErrorWithAction]);

  const handleSend = React.useCallback(() => {
    const text = message;
    setMessage('');
    sendMessage(text);
  }, [message, sendMessage]);

  return (
    <aside
      className={cn(
        'flex-shrink-0 flex-col bg-card border border-border overflow-hidden transition-all duration-300 ease-in-out',
        isMobile ? 'fixed inset-0 z-[100] w-full h-[100dvh] rounded-none border-none flex' : 'rounded-2xl shadow-xl h-full',
        !isMobile && 'hidden lg:flex',
        !isMobile && (isOpen ? 'w-96' : 'w-0 p-0 border-none'),
        className
      )}
    >
      <div
        className={cn(
          'p-3 border-b border-border flex items-center justify-between bg-secondary/30 backdrop-blur-sm h-14 flex-shrink-0',
          !isOpen && !isMobile && 'hidden'
        )}
      >
        <div className="flex items-center gap-3">
          <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-primary/20 to-purple-500/20 flex items-center justify-center relative ring-1 ring-foreground/10">
            <Bot className="text-primary h-5 w-5" />
            <span className="absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 bg-green-500 rounded-full border-2 border-card"></span>
          </div>
          <div>
            <h3 className="text-sm font-bold text-foreground">دستیار هوشمند</h3>
            <p className="text-[10px] text-muted-foreground font-medium">پاسخگوی سوالات شما</p>
          </div>
        </div>
        {isMobile ? (
          <SheetClose asChild>
            <Button
              variant="ghost"
              size="sm"
              className="h-9 px-3 rounded-xl bg-secondary/50 hover:bg-secondary text-muted-foreground hover:text-foreground border border-border/50 transition-all flex items-center gap-2"
            >
              <span className="text-xs font-medium">بستن</span>
              <X className="h-4 w-4" />
            </Button>
          </SheetClose>
        ) : (
          <Button
            onClick={onToggle}
            variant="ghost"
            size="icon"
            className="h-8 w-8 rounded-lg text-muted-foreground hover:text-foreground"
          >
            <PanelRightClose className="h-4 w-4" />
          </Button>
        )}
      </div>
      <div 
        ref={scrollRef}
        className={cn(
          'flex-1 overflow-y-auto p-4 space-y-6 bg-background/30 no-scrollbar min-h-0', 
          !isOpen && !isMobile && 'hidden'
        )}
      >
        {messages.map((m) => (
          <ChatMessage key={m.id} sender={m.sender} time={m.time} message={m.message} widget={m.widget ?? null} />
        ))}
        {isSending && (
          <div className="flex justify-start items-end gap-2 animate-in fade-in slide-in-from-bottom-2 duration-300">
            <div className="h-7 w-7 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0 mb-1">
              <Bot className="h-4 w-4 text-primary" />
            </div>
            <div className="bg-muted px-3 py-2 rounded-[18px] rounded-bl-sm flex items-center gap-1.5 h-9 border border-border/40">
              <span className="w-1.5 h-1.5 bg-primary/60 rounded-full animate-bounce [animation-delay:-0.3s]" />
              <span className="w-1.5 h-1.5 bg-primary/60 rounded-full animate-bounce [animation-delay:-0.15s]" />
              <span className="w-1.5 h-1.5 bg-primary/60 rounded-full animate-bounce" />
            </div>
          </div>
        )}
        {/* Spacer for keyboard on mobile */}
        <div className="h-4 flex-shrink-0" />
      </div>
      <div className={cn('p-3 border-t border-border bg-card z-10 flex-shrink-0', !isOpen && !isMobile && 'hidden')}>
        {chatError && (
          <div className="mb-2 rounded-xl border border-destructive/30 bg-destructive/5 px-3 py-2 flex items-center gap-2">
            <div className="h-7 w-7 rounded-lg bg-destructive/10 text-destructive flex items-center justify-center flex-shrink-0">
              <AlertTriangle className="h-4 w-4" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-xs font-semibold text-foreground truncate">{chatError.title}</div>
              {chatError.detail ? <div className="text-[10px] text-muted-foreground truncate">{chatError.detail}</div> : null}
            </div>
            <div className="flex items-center gap-1 flex-shrink-0">
              {retryAvailable && (
                <Button
                  size="sm"
                  variant="secondary"
                  className="h-7 px-3 text-[10px] font-bold bg-primary/10 hover:bg-primary/20 text-primary border-none"
                  onClick={() => lastActionRef.current?.()}
                >
                  تلاش دوباره
                </Button>
              )}
              <Button
                size="icon"
                variant="ghost"
                className="h-7 w-7 text-muted-foreground hover:text-foreground"
                onClick={clearChatError}
                title="بستن"
              >
                <X className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        )}
        {suggestions.length > 0 && (
          <div className="mb-2 flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 rounded-lg text-muted-foreground hover:text-foreground"
              onClick={() => scrollSuggestions('right')}
              disabled={isSending}
              title="حرکت به راست"
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
            <div ref={suggestionsRef} className="flex-1 overflow-x-auto no-scrollbar">
              <div className="flex gap-2 pb-1">
                {suggestions.slice(0, 6).map((s) => (
                  <Button
                    key={s}
                    variant="outline"
                    className="text-xs h-10 sm:h-8 flex-shrink-0"
                    disabled={isSending}
                    onClick={() => sendMessage(s)}
                  >
                    <MarkdownWithMath
                      markdown={normalizeMathText(s)}
                      className="text-xs [&_.md-p]:m-0 [&_.md-ul]:m-0 [&_.md-ol]:m-0"
                      as="span"
                      renderKey={s}
                    />
                  </Button>
                ))}
              </div>
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 rounded-lg text-muted-foreground hover:text-foreground"
              onClick={() => scrollSuggestions('left')}
              disabled={isSending}
              title="حرکت به چپ"
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
          </div>
        )}

        {isRecording && (
          <div className="mb-2 rounded-xl border border-border bg-primary/5 px-2 py-1.5 flex items-center gap-2 animate-in fade-in slide-in-from-bottom-2 duration-300">
            <div className="h-7 w-7 rounded-lg bg-primary/20 flex items-center justify-center flex-shrink-0">
              <Mic className="h-3.5 w-3.5 text-primary animate-pulse" />
            </div>
            <div className="flex-1 min-w-0 flex items-center gap-2">
              <span className="text-[11px] font-bold text-foreground whitespace-nowrap">{formatDuration(recordSeconds)}</span>
              <div className="flex-1 flex items-center gap-0.5 overflow-hidden h-4">
                {Array.from({ length: 40 }).map((_, i) => (
                  <span
                    key={i}
                    className="w-[2px] rounded-full bg-primary/40 animate-pulse"
                    style={{ 
                      height: `${4 + Math.random() * 12}px`, 
                      animationDelay: `${i * 0.05}s`,
                      opacity: i > 25 ? (40 - i) / 15 : 1
                    }}
                  />
                ))}
              </div>
            </div>
            <Button 
                variant="ghost" 
                size="icon" 
                className="h-7 w-7 text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded-lg" 
                onClick={toggleRecording}
                title="توقف و حذف"
            >
              <X className="h-3.5 w-3.5" />
            </Button>
          </div>
        )}

        {pendingFile && (
          <div className="mb-2 rounded-xl border border-border bg-background/60 shadow-sm px-2 py-1.5 flex items-center gap-2 animate-in fade-in slide-in-from-bottom-2 duration-300">
            <div className="h-7 w-7 rounded-lg bg-secondary flex items-center justify-center flex-shrink-0">
              {pendingFile.type.startsWith('audio/') ? (
                <Mic className="h-3.5 w-3.5 text-primary" />
              ) : (
                <Paperclip className="h-3.5 w-3.5 text-primary -rotate-45" />
              )}
            </div>
            <div className="flex-1 min-w-0 flex items-center gap-2">
              <div className="min-w-0 flex flex-col">
                <span className="text-[10px] font-bold text-foreground truncate">{pendingFile.name}</span>
                <span className="text-[9px] text-muted-foreground leading-tight">
                  {pendingFile.type.startsWith('audio/') && recordedSeconds !== null ? formatDuration(recordedSeconds) : `${(pendingFile.size / 1024).toFixed(1)} KB`}
                </span>
              </div>
              {pendingFile.type.startsWith('audio/') && (
                <div className="flex-1 hidden sm:flex items-center gap-0.5 h-3 px-2 opacity-30">
                  {Array.from({ length: 24 }).map((_, i) => (
                    <span key={i} className="w-[1.5px] rounded-full bg-primary" style={{ height: `${3 + (Math.sin(i * 0.8) + 1) * 4}px` }} />
                  ))}
                </div>
              )}
            </div>
            <div className="flex items-center gap-1 flex-shrink-0">
              <Button
                variant="secondary"
                size="sm"
                className="h-7 px-3 text-[10px] font-bold bg-primary/10 hover:bg-primary/20 text-primary border-none"
                disabled={isSending}
                onClick={handleSend}
              >
                ارسال
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 rounded-lg text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                onClick={() => {
                  setPendingFile(null);
                  setRecordedSeconds(null);
                }}
              >
                <X className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        )}
        <div className="relative">
          <Textarea
            ref={textareaRef}
            value={message}
            onChange={handleInputChange}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            onFocus={() => {
              // Small delay to allow keyboard to open and viewport to resize
              setTimeout(() => {
                if (scrollRef.current) {
                  scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
                }
              }, 300);
            }}
            placeholder="سوالت رو بپرس..."
            rows={1}
            className="bg-background border-border rounded-xl text-sm leading-6 text-foreground focus:ring-1 focus:ring-primary focus:border-primary placeholder:text-muted-foreground/50 py-3 pr-20 pl-12 resize-none overflow-y-hidden no-scrollbar flex items-center min-h-[44px]"
          />
          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            accept="image/*,audio/*"
            onChange={(e) => {
              const f = e.target.files?.[0] ?? null;
              setPendingFile(f);
              setRecordedSeconds(null);
              e.target.value = '';
            }}
          />
          <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 rounded-lg text-muted-foreground hover:text-primary hover:bg-foreground/5"
              title="پیوست فایل"
              disabled={isSending}
              onClick={() => fileInputRef.current?.click()}
            >
              <Paperclip className="h-4 w-4 -rotate-45" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className={cn(
                'h-8 w-8 rounded-lg text-muted-foreground hover:text-primary hover:bg-foreground/5',
                isRecording && 'text-primary'
              )}
              title="ضبط صدا"
              disabled={isSending}
              onClick={toggleRecording}
            >
              <Mic className="h-4 w-4" />
            </Button>
          </div>
          <div className="absolute left-2 top-1/2 -translate-y-1/2 flex items-center">
            <Button
              size="icon"
              className="h-9 w-9 rounded-xl bg-primary hover:bg-primary/90 text-primary-foreground transition-all shadow-lg shadow-primary/20 hover:scale-105 active:scale-95"
              disabled={isSending}
              onClick={handleSend}
            >
              <Send className="h-4 w-4 rtl:-rotate-180" />
            </Button>
          </div>
        </div>
      </div>
    </aside>
  );
};
