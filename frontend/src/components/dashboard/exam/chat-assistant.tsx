'use client';

import React from 'react';
import { Bot, PanelRightClose, Send, Paperclip, Mic, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import { SheetClose } from '@/components/ui/sheet';
import { MarkdownWithMath } from '@/components/content/markdown-with-math';
import { DashboardService } from '@/services/dashboard-service';
import { normalizeMathText } from '@/lib/normalize-math-text';
import type { Question } from '@/types';

interface ChatMessageProps {
  sender: 'ai' | 'user';
  time: string;
  message: string;
}

function formatTime(d: Date): string {
  const hh = d.getHours().toString().padStart(2, '0');
  const mm = d.getMinutes().toString().padStart(2, '0');
  return `${hh}:${mm}`;
}

export const ChatMessage = ({ sender, time, message }: ChatMessageProps) => {
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
          <MarkdownWithMath markdown={normalizeMathText(message)} className="text-sm" renderKey={time} />
        </div>
      </div>
      <span className={`text-[9px] text-muted-foreground ${isAI ? 'pr-11' : 'pl-1'}`}>{time}</span>
    </div>
  );
};

interface ChatAssistantProps {
  onToggle: () => void;
  isOpen: boolean;
  isMobile?: boolean;
  className?: string;
  examId?: string;
  question?: Question | null;
  selectedOptionLabel?: string | null;
  isChecked?: boolean;
}

type ChatApiResponse = { type: 'text'; content: string; suggestions?: string[] };

function normalizeChatResponse(resp: ChatApiResponse | null) {
  const content = String(resp?.content ?? '').trim();
  let suggestions = Array.isArray(resp?.suggestions) ? resp?.suggestions : [];

  if (content.startsWith('{') && content.includes('"content"')) {
    try {
      const parsed = JSON.parse(content);
      const nestedContent = String(parsed?.content ?? '').trim();
      if (nestedContent) {
        return {
          content: nestedContent,
          suggestions: Array.isArray(parsed?.suggestions) ? parsed.suggestions : suggestions,
        };
      }
    } catch {
      // ignore
    }
  }

  return { content, suggestions };
}

export const ChatAssistant = ({ onToggle, isOpen, isMobile = false, className, examId, question, selectedOptionLabel, isChecked }: ChatAssistantProps) => {
  const [message, setMessage] = React.useState('');
  const [messages, setMessages] = React.useState<Array<{ id: string; sender: 'ai' | 'user'; time: string; message: string }>>([]);
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
    const base = String(examId ?? '').trim();
    const qid = String(question?.id ?? '').trim();
    return `${base}:${qid || 'root'}`;
  }, [examId, question?.id]);

  const selectedLabel = React.useMemo(() => {
    return String(selectedOptionLabel ?? '').trim();
  }, [selectedOptionLabel]);

  // Exam Prep must never expose correct answers client-side.
  // Correctness (if needed) is computed server-side.
  const isCorrect = false;

  const handleInputChange = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
    setMessage(event.target.value);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  };

  React.useEffect(() => {
    if (isOpen && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [isOpen, messages]);

  React.useEffect(() => {
    setMessages([]);
    setSuggestions([]);
    setPendingFile(null);
    setMessage('');
    setHistoryLoaded(false);
  }, [threadKey]);

  React.useEffect(() => {
    if (!isOpen) return;
    const eid = String(examId ?? '').trim();
    if (!eid || historyLoaded) return;

    let cancelled = false;

    const run = async () => {
      try {
        const hist = await DashboardService.getExamPrepChatHistory(eid, question?.id ?? null);
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
            return {
              id: `hist-${String(it?.id ?? Math.random())}`,
              sender,
              time: formatTime(createdAt),
              message: String(it?.content ?? ''),
            };
          });

        setMessages(mapped);
      } catch {
        // ignore
      } finally {
        if (!cancelled) setHistoryLoaded(true);
      }
    };

    run();

    return () => {
      cancelled = true;
    };
  }, [isOpen, examId, question?.id, historyLoaded]);

  const sendMessage = async (text: string) => {
    const msg = String(text ?? '').trim();
    const eid = String(examId ?? '').trim();
    if (!msg || !eid || isSending) return;

    setIsSending(true);
    const userMsg = { id: `user-${Date.now()}`, sender: 'user' as const, time: formatTime(new Date()), message: msg };
    setMessages(prev => [...prev, userMsg]);
    setMessage('');

    try {
      const resp = (await DashboardService.sendExamPrepChatMessage(eid, {
        message: msg,
        question_id: question?.id ?? null,
        student_selected: selectedLabel,
        is_checked: Boolean(isChecked),
      })) as ChatApiResponse;

      const normalized = normalizeChatResponse(resp);
      const content = normalizeMathText(normalized.content);
      if (content) {
        const aiMsg = { id: `ai-${Date.now()}`, sender: 'ai' as const, time: formatTime(new Date()), message: content };
        setMessages(prev => [...prev, aiMsg]);
      }
      setSuggestions(Array.isArray(normalized.suggestions) ? normalized.suggestions : []);
        // Re-fetch persisted history so the chat stays in sync with backend storage.
        setHistoryLoaded(false);
    } catch {
      const aiMsg = {
        id: `ai-${Date.now()}`,
        sender: 'ai' as const,
        time: formatTime(new Date()),
        message: 'الان در پاسخگویی مشکلی پیش آمده. لطفاً دوباره تلاش کن.',
      };
      setMessages(prev => [...prev, aiMsg]);
    } finally {
      setIsSending(false);
    }
  };

  const handleSend = () => {
    if (pendingFile) {
      void handleUpload(pendingFile);
      return;
    }
    void sendMessage(message);
  };

  const handleUpload = async (file: File) => {
    const eid = String(examId ?? '').trim();
    if (!eid) return;

    setIsSending(true);
    const formData = new FormData();
    formData.append('file', file);
    formData.append('message', message || '');
    formData.append('question_id', question?.id ?? '');
    formData.append('student_selected', selectedLabel || '');
    formData.append('is_checked', String(Boolean(isChecked)));

    try {
      const resp = (await DashboardService.sendExamPrepChatMedia(eid, formData)) as ChatApiResponse;
      const normalized = normalizeChatResponse(resp);
      const content = normalizeMathText(normalized.content);
      if (content) {
        const aiMsg = { id: `ai-${Date.now()}`, sender: 'ai' as const, time: formatTime(new Date()), message: content };
        setMessages(prev => [...prev, aiMsg]);
      }
      setSuggestions(Array.isArray(normalized.suggestions) ? normalized.suggestions : []);
      // Re-fetch persisted history so the chat stays in sync with backend storage.
      setHistoryLoaded(false);
    } catch {
      const aiMsg = {
        id: `ai-${Date.now()}`,
        sender: 'ai' as const,
        time: formatTime(new Date()),
        message: 'در پردازش فایل مشکلی پیش آمد. دوباره تلاش کن.',
      };
      setMessages(prev => [...prev, aiMsg]);
    } finally {
      setIsSending(false);
      setPendingFile(null);
      setMessage('');
    }
  };

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setPendingFile(file);
  };

  const handleSuggestion = (s: string) => {
    void sendMessage(s);
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  };

  const startRecording = async () => {
    try {
      if (!navigator?.mediaDevices?.getUserMedia) return;
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      recordChunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) recordChunksRef.current.push(e.data);
      };
      recorder.onstop = async () => {
        const blob = new Blob(recordChunksRef.current, { type: 'audio/webm' });
        const file = new File([blob], 'recording.webm', { type: 'audio/webm' });
        await handleUpload(file);
        stream.getTracks().forEach(t => t.stop());
      };
      recorder.start();
      recorderRef.current = recorder;
      recordStartRef.current = Date.now();
      setIsRecording(true);
      setRecordSeconds(0);
    } catch {
      // ignore
    }
  };

  const stopRecording = () => {
    if (recorderRef.current && isRecording) {
      recorderRef.current.stop();
      recorderRef.current = null;
      setIsRecording(false);
    }
  };

  React.useEffect(() => {
    if (!isRecording) return;
    const id = setInterval(() => {
      if (!recordStartRef.current) return;
      const elapsed = Math.floor((Date.now() - recordStartRef.current) / 1000);
      setRecordSeconds(elapsed);
    }, 500);
    return () => clearInterval(id);
  }, [isRecording]);

  return (
    <aside
      className={cn(
        'flex-shrink-0 flex-col bg-card border-border overflow-hidden transition-all duration-300 ease-in-out',
        isMobile ? 'flex w-full h-[100dvh] rounded-none border-none' : 'rounded-l-2xl shadow-xl h-full border-l',
        !isMobile && 'hidden md:flex',
        !isMobile && (isOpen ? 'w-[36rem]' : 'w-0 p-0 border-none'),
        className
      )}
    >
      <div
        className={cn(
          'p-4 border-b border-border flex items-center justify-between bg-secondary/30 backdrop-blur-sm h-[73px] flex-shrink-0',
          !isOpen && !isMobile && 'hidden'
        )}
      >
        <div className="flex items-center gap-3">
          <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-primary/20 to-purple-500/20 flex items-center justify-center relative ring-1 ring-foreground/10">
            <Bot className="text-primary h-5 w-5" />
            <span className="absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 bg-green-500 rounded-full border-2 border-card"></span>
          </div>
          <div>
            <h3 className="text-sm font-bold text-foreground text-right">دستیار هوشمند</h3>
            <p className="text-[10px] text-muted-foreground font-medium">راهنمای حل سؤال</p>
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
          <button
            onClick={onToggle}
            className="h-8 w-8 rounded-lg text-muted-foreground hover:text-foreground flex items-center justify-center"
          >
            <PanelRightClose className="h-4 w-4" />
          </button>
        )}
      </div>
      <div
        ref={scrollRef}
        className={cn(
          'flex-1 overflow-y-auto p-4 space-y-6 bg-background/30 no-scrollbar min-h-0',
          !isOpen && !isMobile && 'hidden'
        )}
      >
        {messages.length === 0 ? (
          <ChatMessage
            sender="ai"
            time={formatTime(new Date())}
            message="سلام! 👋 من دستیار هوشمندت هستم. می‌تونیم قدم‌به‌قدم برای حل این سوال جلو بریم."
          />
        ) : null}
        {messages.map(m => (
          <ChatMessage key={m.id} sender={m.sender} time={m.time} message={m.message} />
        ))}
        <div className="h-4 flex-shrink-0" />
      </div>
      <div className={cn('p-3 border-t border-border bg-card z-10 flex-shrink-0', !isOpen && !isMobile && 'hidden')}>
        <div className="flex gap-2 mb-2 overflow-x-auto no-scrollbar pb-1">
          {(suggestions.length ? suggestions : ['راهنمایی می‌خوام', 'قدم اول چیه؟', 'یه مثال مشابه بزن']).map(s => (
            <Button key={s} variant="outline" className="text-xs h-8 flex-shrink-0" onClick={() => handleSuggestion(s)} disabled={isSending}>
              <MarkdownWithMath
                markdown={normalizeMathText(s)}
                className="text-xs [&_.md-p]:m-0 [&_.md-ul]:m-0 [&_.md-ol]:m-0"
                as="span"
                renderKey={s}
              />
            </Button>
          ))}
        </div>
        <div className="relative">
          <Textarea
            ref={textareaRef}
            value={message}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            onFocus={() => {
              setTimeout(() => {
                if (scrollRef.current) {
                  scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
                }
              }, 300);
            }}
            placeholder="سوالت رو بپرس... یا تصویر تمرینت رو بفرست"
            rows={1}
            className="bg-background border-border rounded-xl text-sm text-foreground focus:ring-1 focus:ring-primary focus:border-primary placeholder:text-muted-foreground/50 py-3 pl-12 pr-20 resize-none overflow-y-hidden no-scrollbar"
          />
          <div className="absolute left-2 bottom-1.5 flex items-center">
            <Button
              size="icon"
              className="h-9 w-9 rounded-xl bg-primary hover:bg-primary/90 text-primary-foreground transition-all shadow-lg shadow-primary/20 hover:scale-105 active:scale-95"
              onClick={handleSend}
              disabled={isSending}
              title="ارسال"
            >
              <Send className="h-4 w-4 rtl:-rotate-180" />
            </Button>
          </div>
          <div className="absolute right-2 bottom-1.5 flex items-center gap-1">
            <input ref={fileInputRef} type="file" className="hidden" onChange={handleFileChange} />
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 rounded-lg text-muted-foreground hover:text-primary hover:bg-foreground/5"
              title="پیوست فایل"
              onClick={() => fileInputRef.current?.click()}
              disabled={isSending}
            >
              <Paperclip className="h-4 w-4 -rotate-45" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className={cn('h-8 w-8 rounded-lg text-muted-foreground hover:text-primary hover:bg-foreground/5', isRecording && 'text-primary')}
              title={isRecording ? `در حال ضبط (${recordSeconds}s)` : 'ضبط صدا'}
              onClick={() => (isRecording ? stopRecording() : startRecording())}
              disabled={isSending}
            >
              <Mic className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>
    </aside>
  );
};
