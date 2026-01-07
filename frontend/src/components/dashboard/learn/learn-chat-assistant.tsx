'use client';

import React from 'react';
import { Bot, PanelRightClose, Send, Paperclip, Mic, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import { SheetClose } from '@/components/ui/sheet';
import { MarkdownWithMath } from '@/components/content/markdown-with-math';
import { DashboardService } from '@/services/dashboard-service';

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

function WidgetCard({ widgetType, data }: { widgetType: string; data: any }) {
  const type = String(widgetType || '').trim();

  const title =
    type === 'quiz'
      ? 'کوئیز'
      : type === 'flashcard'
        ? 'فلش‌کارت'
        : type === 'match_game'
          ? 'بازی تطبیق'
          : type === 'notes'
            ? 'جزوه و نکات'
            : type === 'scenario'
              ? 'سناریو'
              : type === 'practice_test'
                ? 'آزمون تمرینی'
                : type === 'image'
                  ? 'ایده‌ی تصویر'
                  : 'ابزار';

  const renderList = (items: any[], renderItem: (item: any, idx: number) => React.ReactNode) => {
    if (!Array.isArray(items) || items.length === 0) {
      return <div className="text-xs text-muted-foreground">موردی برای نمایش نیست.</div>;
    }
    return <div className="space-y-2">{items.slice(0, 6).map(renderItem)}</div>;
  };

  return (
    <div className="mt-2 rounded-xl border border-border bg-card p-3">
      <div className="text-xs font-bold text-foreground mb-2">{title}</div>

      {type === 'quiz' &&
        renderList(data?.questions, (q, idx) => (
          <div key={idx} className="rounded-lg bg-background/40 border border-border/50 p-2">
            <div className="text-xs font-medium mb-1">{String(q?.question ?? '')}</div>
            {Array.isArray(q?.options) && q.options.length > 0 && (
              <div className="text-[11px] text-muted-foreground space-y-1">
                {q.options.slice(0, 4).map((opt: any, i: number) => (
                  <div key={i}>• {String(opt)}</div>
                ))}
              </div>
            )}
          </div>
        ))}

      {type === 'flashcard' &&
        renderList(data?.flashcards, (c, idx) => (
          <div key={idx} className="rounded-lg bg-background/40 border border-border/50 p-2">
            <div className="text-xs font-medium mb-1">{String(c?.front ?? '')}</div>
            <div className="text-[11px] text-muted-foreground">{String(c?.back ?? '')}</div>
          </div>
        ))}

      {type === 'match_game' &&
        renderList(data?.pairs, (p, idx) => (
          <div key={idx} className="rounded-lg bg-background/40 border border-border/50 p-2">
            <div className="text-xs font-medium">{String(p?.term ?? '')}</div>
            <div className="text-[11px] text-muted-foreground">{String(p?.definition ?? '')}</div>
          </div>
        ))}

      {type === 'notes' &&
        renderList(data?.items, (it, idx) => (
          <div key={idx} className="rounded-lg bg-background/40 border border-border/50 p-2">
            <MarkdownWithMath markdown={String(it?.notes_markdown ?? it?.summary_markdown ?? '')} className="text-[11px]" />
          </div>
        ))}

      {type === 'scenario' &&
        renderList(data?.scenarios, (s, idx) => (
          <div key={idx} className="rounded-lg bg-background/40 border border-border/50 p-2">
            <div className="text-xs font-medium mb-1">{String(s?.title ?? '')}</div>
            <div className="text-[11px] text-muted-foreground">{String(s?.challenge_question ?? '')}</div>
          </div>
        ))}

      {type === 'practice_test' &&
        renderList(data?.test_items, (t, idx) => (
          <div key={idx} className="rounded-lg bg-background/40 border border-border/50 p-2">
            <div className="text-xs font-medium mb-1">{String(t?.question ?? '')}</div>
            {Array.isArray(t?.options) && t.options.length > 0 && (
              <div className="text-[11px] text-muted-foreground">{t.options.map(String).join(' | ')}</div>
            )}
          </div>
        ))}

      {type === 'image' &&
        renderList(data?.images, (im, idx) => (
          <div key={idx} className="rounded-lg bg-background/40 border border-border/50 p-2">
            <div className="text-[11px] text-muted-foreground mb-2">{String(im?.caption ?? '')}</div>
            <div className="text-[11px] font-mono break-words" dir="ltr">
              {String(im?.prompt ?? '')}
            </div>
          </div>
        ))}
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
            'p-3 rounded-2xl leading-6 shadow-sm border max-w-[90%]',
            isAI ? 'bg-card text-foreground rounded-tr-none border-border/50' : 'bg-primary/10 text-foreground rounded-tl-none border-primary/20'
          )}
        >
          <MarkdownWithMath markdown={message} className="text-sm" />
          {isAI && widget?.widget_type ? <WidgetCard widgetType={widget.widget_type} data={widget.data} /> : null}
        </div>
      </div>
      <span className={`text-[9px] text-muted-foreground ${isAI ? 'pr-11' : 'pl-1'}`}>{time}</span>
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
}

type ChatApiResponse =
  | { type: 'text'; content: string; suggestions?: string[] }
  | { type: 'widget'; widget_type: string; data: any; text?: string; suggestions?: string[] };

export const ChatAssistant = ({ onToggle, isOpen, className, isMobile = false, courseId, lessonId, lessonTitle, pageContext, pageMaterial }: ChatAssistantProps) => {
  const [message, setMessage] = React.useState('');
  const [messages, setMessages] = React.useState<
    Array<{ id: string; sender: 'ai' | 'user'; time: string; message: string; widget?: { widget_type: string; data: any } | null }>
  >([]);
  const [suggestions, setSuggestions] = React.useState<string[]>([]);
  const [pendingFile, setPendingFile] = React.useState<File | null>(null);
  const [isSending, setIsSending] = React.useState(false);
  const [historyLoaded, setHistoryLoaded] = React.useState(false);

  const [isRecording, setIsRecording] = React.useState(false);
  const recorderRef = React.useRef<MediaRecorder | null>(null);
  const recordChunksRef = React.useRef<BlobPart[]>([]);
  const recordStartRef = React.useRef<number | null>(null);
  const [recordSeconds, setRecordSeconds] = React.useState(0);

  const textareaRef = React.useRef<HTMLTextAreaElement>(null);
  const scrollRef = React.useRef<HTMLDivElement>(null);
  const fileInputRef = React.useRef<HTMLInputElement>(null);

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

  // Scroll to bottom on open or new messages
  React.useEffect(() => {
    if (isOpen && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [isOpen]);

  // Reset chat when lesson/thread changes (legacy behavior: thread_id includes unit).
  React.useEffect(() => {
    setMessages([]);
    setSuggestions([]);
    setPendingFile(null);
    setMessage('');
    setHistoryLoaded(false);
  }, [threadKey]);

  // Load persisted history from backend (so student sees previous chat after returning).
  React.useEffect(() => {
    if (!isOpen) return;
    const cid = String(courseId ?? '').trim();
    if (!cid) return;

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

        // Legacy rule: only update suggestions if server provides them.
        const last = items.length > 0 ? items[items.length - 1] : null;
        const nextSuggestions = Array.isArray(last?.suggestions) ? last.suggestions.filter(Boolean) : [];
        if (nextSuggestions.length > 0) {
          setSuggestions(nextSuggestions);
        }
      } catch {
        // Ignore history load failures; chat still works.
      } finally {
        if (!cancelled) setHistoryLoaded(true);
      }
    };

    run();

    return () => {
      cancelled = true;
    };
  }, [isOpen, courseId, lessonId, threadKey]);

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
          resp = (await DashboardService.sendCourseChatMedia(cid, fd)) as ChatApiResponse;
        } else {
          resp = (await DashboardService.sendCourseChatMessage(cid, {
            message: msg,
            lesson_id: lessonId ?? null,
            page_context: pageContext ?? '',
            page_material: pageMaterial ?? '',
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
        // Legacy rule: only update suggestions if server provides them.
        if (nextSuggestions.length > 0) {
          setSuggestions(nextSuggestions);
        }
        setPendingFile(null);
      } catch (e) {
        const msgErr = e instanceof Error ? e.message : 'خطا در ارسال پیام';
        pushMessage({ sender: 'ai', message: msgErr });
      } finally {
        setIsSending(false);
      }
    },
    [courseId, isSending, isProtocolMessage, lessonId, pageContext, pageMaterial, pendingFile, pushMessage]
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
      };

      rec.start();
      setIsRecording(true);
    } catch (e) {
      const msgErr = e instanceof Error ? e.message : 'خطا در دسترسی به میکروفون';
      pushMessage({ sender: 'ai', message: msgErr });
    }
  }, [isRecording, isSending, pushMessage]);

  return (
    <aside
      className={cn(
        'flex-shrink-0 flex-col bg-card border border-border overflow-hidden transition-all duration-300 ease-in-out',
        isMobile ? 'fixed inset-0 z-[100] w-full h-[100dvh] rounded-none border-none flex' : 'rounded-2xl shadow-xl h-full',
        !isMobile && 'hidden md:flex',
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
        {/* Spacer for keyboard on mobile */}
        <div className="h-4 flex-shrink-0" />
      </div>
      <div className={cn('p-3 border-t border-border bg-card z-10 flex-shrink-0', !isOpen && !isMobile && 'hidden')}>
        {suggestions.length > 0 && (
          <div className="flex gap-2 mb-2 overflow-x-auto no-scrollbar pb-1">
            {suggestions.slice(0, 6).map((s) => (
              <Button
                key={s}
                variant="outline"
                className="text-xs h-8 flex-shrink-0"
                disabled={isSending}
                onClick={() => sendMessage(s)}
              >
                {s}
              </Button>
            ))}
          </div>
        )}

        {pendingFile && (
          <div className="mb-2 flex items-center justify-between gap-2 rounded-xl border border-border bg-background/40 px-3 py-2">
            <div className="text-xs text-muted-foreground truncate">
              فایل: <span className="text-foreground">{pendingFile.name}</span>
            </div>
            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setPendingFile(null)}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        )}

        {isRecording && (
          <div className="mb-2 text-xs text-muted-foreground">
            در حال ضبط صدا… ({recordSeconds}s)
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
                const text = message;
                setMessage('');
                sendMessage(text);
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
            placeholder="سوالت رو بپرس... یا تصویر تمرینت رو بفرست"
            rows={1}
            className="bg-background border-border rounded-xl text-sm text-foreground focus:ring-1 focus:ring-primary focus:border-primary placeholder:text-muted-foreground/50 py-3 pr-20 pl-12 resize-none overflow-y-hidden no-scrollbar"
          />
          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            accept="image/*,audio/*"
            onChange={(e) => {
              const f = e.target.files?.[0] ?? null;
              setPendingFile(f);
              e.target.value = '';
            }}
          />
          <div className="absolute right-2 bottom-1.5 flex items-center gap-1">
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
          <div className="absolute left-2 bottom-1.5 flex items-center">
            <Button
              size="icon"
              className="h-9 w-9 rounded-xl bg-primary hover:bg-primary/90 text-primary-foreground transition-all shadow-lg shadow-primary/20 hover:scale-105 active:scale-95"
              disabled={isSending}
              onClick={() => {
                const text = message;
                setMessage('');
                sendMessage(text);
              }}
            >
              <Send className="h-4 w-4 rtl:-rotate-180" />
            </Button>
          </div>
        </div>
      </div>
    </aside>
  );
};
