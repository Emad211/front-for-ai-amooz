'use client';

import { Users, User, Search, Check } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { MessageRecipient } from '@/types';

interface RecipientSelectorProps {
  audience: 'all' | 'students' | 'teachers';
  onAudienceChange: (type: 'all' | 'students' | 'teachers') => void;
  recipients: MessageRecipient[];
  searchQuery: string;
  onSearchChange: (query: string) => void;
}

export function RecipientSelector({
  audience,
  onAudienceChange,
  recipients,
  searchQuery,
  onSearchChange,
}: RecipientSelectorProps) {
  const normalizedQuery = searchQuery.toLowerCase();
  const scopedRecipients = recipients.filter((recipient) => {
    if (audience === 'students') return recipient.role === 'student';
    if (audience === 'teachers') return recipient.role === 'teacher';
    return true;
  });

  const filteredRecipients = scopedRecipients.filter((recipient) =>
    recipient.name.toLowerCase().includes(normalizedQuery) ||
    recipient.email.toLowerCase().includes(normalizedQuery)
  );

  return (
    <div className="space-y-6">
      <div className="space-y-4">
        <Label>گیرندگان</Label>
        <RadioGroup 
          value={audience} 
          onValueChange={(v) => onAudienceChange(v as 'all' | 'students' | 'teachers')}
          className="grid grid-cols-1 sm:grid-cols-3 gap-4"
        >
          <div 
            className={cn(
              "flex items-center gap-3 border-2 rounded-2xl p-4 cursor-pointer transition-all duration-200 hover:border-primary/50",
              audience === 'all' ? "border-primary bg-primary/5 shadow-sm" : "border-border bg-card"
            )}
            onClick={() => onAudienceChange('all')}
          >
            <RadioGroupItem value="all" id="all" className="sr-only" />
            <div className={cn(
              "h-10 w-10 rounded-xl flex items-center justify-center transition-colors",
              audience === 'all' ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
            )}>
              <Users className="h-5 w-5" />
            </div>
            <div className="flex-1">
              <Label htmlFor="all" className="cursor-pointer font-bold block">همه کاربران</Label>
              <p className="text-[10px] text-muted-foreground">ارسال به دانش‌آموزان و معلمان</p>
            </div>
            {audience === 'all' && <Check className="h-5 w-5 text-primary" />}
          </div>

          <div 
            className={cn(
              "flex items-center gap-3 border-2 rounded-2xl p-4 cursor-pointer transition-all duration-200 hover:border-primary/50",
              audience === 'students' ? "border-primary bg-primary/5 shadow-sm" : "border-border bg-card"
            )}
            onClick={() => onAudienceChange('students')}
          >
            <RadioGroupItem value="students" id="students" className="sr-only" />
            <div className={cn(
              "h-10 w-10 rounded-xl flex items-center justify-center transition-colors",
              audience === 'students' ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
            )}>
              <User className="h-5 w-5" />
            </div>
            <div className="flex-1">
              <Label htmlFor="students" className="cursor-pointer font-bold block">دانش‌آموزان</Label>
              <p className="text-[10px] text-muted-foreground">ارسال فقط برای دانش‌آموزان</p>
            </div>
            {audience === 'students' && <Check className="h-5 w-5 text-primary" />}
          </div>

          <div 
            className={cn(
              "flex items-center gap-3 border-2 rounded-2xl p-4 cursor-pointer transition-all duration-200 hover:border-primary/50",
              audience === 'teachers' ? "border-primary bg-primary/5 shadow-sm" : "border-border bg-card"
            )}
            onClick={() => onAudienceChange('teachers')}
          >
            <RadioGroupItem value="teachers" id="teachers" className="sr-only" />
            <div className={cn(
              "h-10 w-10 rounded-xl flex items-center justify-center transition-colors",
              audience === 'teachers' ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
            )}>
              <Users className="h-5 w-5" />
            </div>
            <div className="flex-1">
              <Label htmlFor="teachers" className="cursor-pointer font-bold block">معلمان</Label>
              <p className="text-[10px] text-muted-foreground">ارسال فقط برای معلمان</p>
            </div>
            {audience === 'teachers' && <Check className="h-5 w-5 text-primary" />}
          </div>
        </RadioGroup>
      </div>

      <div className="border-2 border-dashed rounded-2xl p-4 space-y-4 bg-muted/30 animate-in fade-in slide-in-from-top-4 duration-300">
        <div className="relative">
          <Search className="absolute start-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input 
            placeholder="جستجوی کاربر..." 
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            className="bg-background h-12 rounded-xl ps-10 border-none shadow-sm"
          />
        </div>

        <div className="flex items-center justify-between text-sm text-muted-foreground px-1">
          <span>{filteredRecipients.length} نفر</span>
        </div>

        <ScrollArea className="h-[200px] rounded-lg border bg-background p-2">
          <div className="space-y-2">
            {filteredRecipients.map((recipient) => (
              <div 
                key={recipient.id}
                className="flex items-center gap-3 p-3 rounded-xl hover:bg-secondary/50 transition-colors"
              >
                <Avatar className="h-8 w-8">
                  <AvatarImage src={recipient.avatar} />
                  <AvatarFallback>{recipient.name[0]}</AvatarFallback>
                </Avatar>
                <div className="flex-1">
                  <p className="text-sm font-medium">{recipient.name}</p>
                  <p className="text-xs text-muted-foreground">{recipient.email}</p>
                </div>
                <span className="text-[10px] text-muted-foreground">
                  {recipient.role === 'teacher' ? 'معلم' : 'دانش‌آموز'}
                </span>
              </div>
            ))}
            {filteredRecipients.length === 0 && (
              <div className="text-center py-8 text-muted-foreground text-sm">
                کاربری یافت نشد
              </div>
            )}
          </div>
        </ScrollArea>
      </div>
    </div>
  );
}
