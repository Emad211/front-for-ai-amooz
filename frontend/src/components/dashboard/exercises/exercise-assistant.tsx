'use client';

/** Section-aware exercise assistant chat widget. */
import { useState } from 'react';
import { toast } from 'sonner';
import { Loader2, Send } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { MarkdownWithMath } from '@/components/content/markdown-with-math';
import { askAssistant } from '@/services/exercises-service';

type ChatTurn = { role: 'user' | 'assistant'; content: string };

export function ExerciseAssistant({
  sessionId,
  exerciseId,
  questionId,
}: {
  sessionId: number;
  exerciseId: number;
  questionId: number;
}) {
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);

  const send = async () => {
    const text = message.trim();
    if (!text || busy) return;
    setMessage('');
    setTurns((prev) => [...prev, { role: 'user', content: text }]);
    setBusy(true);
    try {
      const reply = await askAssistant(sessionId, exerciseId, questionId, text);
      setTurns((prev) => [...prev, { role: 'assistant', content: reply.content }]);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'دستیار پاسخ نداد.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="flex h-[28rem] flex-col">
      <CardHeader className="py-3">
        <CardTitle className="text-sm">دستیار هوشمند</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-2 overflow-hidden">
        <div className="flex-1 space-y-2 overflow-y-auto text-sm">
          {turns.length === 0 && (
            <p className="text-muted-foreground">برای راهنمایی در حلِ این بخش، سؤالت را بپرس.</p>
          )}
          {turns.map((t, i) => (
            <div
              key={i}
              className={`rounded-md px-3 py-2 ${
                t.role === 'user' ? 'bg-primary/10' : 'bg-muted'
              }`}
            >
              <MarkdownWithMath markdown={t.content} />
            </div>
          ))}
          {busy && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />}
        </div>
        <div className="flex items-center gap-2">
          <Input
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') void send();
            }}
            placeholder="سؤالت را بنویس…"
          />
          <Button size="icon" onClick={send} disabled={busy} aria-label="ارسال">
            <Send className="h-4 w-4" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
