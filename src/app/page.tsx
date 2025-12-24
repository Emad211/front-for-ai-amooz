"use client";

import { useState, useEffect, useCallback } from 'react';
import { Timer, Maximize, Minimize, NotepadText, Play, Pause, RotateCcw, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';

export default function Home() {
  const [time, setTime] = useState(0);
  const [isRunning, setIsRunning] = useState(false);
  const [notes, setNotes] = useState('');
  const [isClient, setIsClient] = useState(false);
  
  const [showTimer, setShowTimer] = useState(true);
  const [showNotes, setShowNotes] = useState(true);
  const [isZenMode, setIsZenMode] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);

  useEffect(() => {
    setIsClient(true);
  }, []);

  // Timer logic
  useEffect(() => {
    let interval: NodeJS.Timeout | null = null;
    if (isRunning) {
      interval = setInterval(() => {
        setTime(prevTime => prevTime + 1);
      }, 1000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isRunning]);

  const formatTime = (seconds: number) => {
    const getSeconds = `0${seconds % 60}`.slice(-2);
    const minutes = Math.floor(seconds / 60);
    const getMinutes = `0${minutes % 60}`.slice(-2);
    const getHours = `0${Math.floor(seconds / 3600)}`.slice(-2);
    return `${getHours}:${getMinutes}:${getSeconds}`;
  };

  const handleToggleTimer = () => setIsRunning(!isRunning);
  const handleResetTimer = () => {
    setTime(0);
    setIsRunning(false);
  };

  // Fullscreen logic
  const toggleFullscreen = useCallback(() => {
    if (!isClient) return;
    const element = document.documentElement;
    if (!document.fullscreenElement) {
      element.requestFullscreen().catch(err => {
        console.error(`Error attempting to enable full-screen mode: ${err.message} (${err.name})`);
      });
    } else {
      if (document.exitFullscreen) {
        document.exitFullscreen();
      }
    }
  }, [isClient]);

  useEffect(() => {
    if (!isClient) return;
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, [isClient]);
  
  if (!isClient) {
    // Render a black screen on server to avoid flash of different content
    return <main className="h-dvh w-screen bg-background"></main>;
  }

  return (
    <TooltipProvider>
      <main className="relative flex h-dvh w-screen flex-col items-center justify-center bg-background text-accent p-4 overflow-hidden"
            onClick={() => isZenMode && setIsZenMode(false)}>
        
        {/* Controls Bar */}
        <div className={cn(
          "absolute top-4 right-4 flex items-center gap-2 transition-opacity duration-300",
          isZenMode && "opacity-0 pointer-events-none"
        )}>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="ghost" size="icon" onClick={(e) => { e.stopPropagation(); setShowTimer(!showTimer); }}>
                <Timer className={cn("h-5 w-5", !showTimer && "text-muted-foreground")} />
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              <p>Toggle Timer</p>
            </TooltipContent>
          </Tooltip>
          
          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="ghost" size="icon" onClick={(e) => { e.stopPropagation(); setShowNotes(!showNotes); }}>
                <NotepadText className={cn("h-5 w-5", !showNotes && "text-muted-foreground")} />
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              <p>Toggle Notes</p>
            </TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="ghost" size="icon" onClick={(e) => { e.stopPropagation(); setIsZenMode(true); }}>
                <Sparkles className="h-5 w-5" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              <p>Zen Mode (Show only notes)</p>
            </TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="ghost" size="icon" onClick={(e) => { e.stopPropagation(); toggleFullscreen(); }}>
                {isFullscreen ? <Minimize className="h-5 w-5" /> : <Maximize className="h-5 w-5" />}
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              <p>{isFullscreen ? 'Exit Fullscreen' : 'Enter Fullscreen'}</p>
            </TooltipContent>
          </Tooltip>
        </div>

        {/* Timer Display */}
        <div className={cn(
          "absolute top-4 left-4 flex items-center gap-4 text-accent transition-opacity duration-300",
          (!showTimer || isZenMode) && "opacity-0 pointer-events-none"
        )}>
          <p className="text-5xl font-mono font-light tabular-nums tracking-widest">{formatTime(time)}</p>
          <div className="flex flex-col gap-1">
            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={(e) => { e.stopPropagation(); handleToggleTimer(); }}>
              {isRunning ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
              <span className="sr-only">{isRunning ? 'Pause' : 'Play'} Timer</span>
            </Button>
            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={(e) => { e.stopPropagation(); handleResetTimer(); }}>
              <RotateCcw className="h-4 w-4" />
              <span className="sr-only">Reset Timer</span>
            </Button>
          </div>
        </div>

        {/* Notes Area */}
        <div className={cn(
          "w-full max-w-2xl flex-grow flex flex-col justify-center items-center transition-opacity duration-300",
          !showNotes && !isZenMode && "opacity-0 pointer-events-none"
        )}>
          {isZenMode ? (
             <div className="text-2xl md:text-3xl text-center leading-relaxed whitespace-pre-wrap animate-in fade-in"
                  key={notes}>
               {notes}
             </div>
          ) : (
             <Textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Begin your session..."
                onClick={(e) => e.stopPropagation()}
                className={cn(
                  "w-full h-full bg-transparent border-none text-accent placeholder:text-muted-foreground focus-visible:ring-0 focus-visible:ring-offset-0 resize-none text-2xl md:text-3xl text-center leading-relaxed",
                  !showNotes && "opacity-0 pointer-events-none"
                )}
             />
          )}
        </div>

        {isZenMode && (
          <div className="absolute bottom-4 text-xs text-muted-foreground animate-in fade-in">
            Click anywhere to exit Zen Mode
          </div>
        )}
      </main>
    </TooltipProvider>
  );
}
