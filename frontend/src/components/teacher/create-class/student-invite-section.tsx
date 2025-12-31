'use client';

import { useState } from 'react';
import { Users, ChevronDown, Copy, Check, Plus, User, Trash2 } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { cn } from '@/lib/utils';

interface Student {
  phone: string;
  avatar: string;
  inviteCode: string;
}

interface StudentInviteSectionProps {
  isExpanded: boolean;
  onToggle: () => void;
}

export function StudentInviteSection({ isExpanded, onToggle }: StudentInviteSectionProps) {
  const [invitedStudents, setInvitedStudents] = useState<Student[]>([{
    phone: '09120000001',
    avatar: 'https://picsum.photos/seed/s1/40/40',
    inviteCode: generateStableInviteCode('09120000001'),
  }]);
  const [newPhone, setNewPhone] = useState('');
  const [copiedCode, setCopiedCode] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const normalizePhone = (input: string) => {
    const digits = input.replace(/\D/g, '');
    if (digits.startsWith('98') && digits.length === 12) return `0${digits.slice(2)}`;
    if (digits.length === 10 && digits.startsWith('9')) return `0${digits}`;
    return digits;
  };

  const isValidPhone = (phone: string) => /^09\d{9}$/.test(phone);

  function generateStableInviteCode(phone: string) {
    const digits = phone.replace(/\D/g, '');
    const suffix = digits.slice(-6).padStart(6, '0');
    const hashSeed = digits
      .split('')
      .reduce((acc, cur, idx) => (acc + (parseInt(cur, 10) + idx * 7)) % 100000, 0)
      .toString()
      .padStart(5, '0');
    return `INV-${suffix}-${hashSeed}`.toUpperCase();
  }

  const handleAddStudent = () => {
    const normalized = normalizePhone(newPhone.trim());

    if (!isValidPhone(normalized)) {
      setErrorMessage('شماره تلفن نامعتبر است. مثال: 09120000000');
      return;
    }

    if (invitedStudents.find(s => s.phone === normalized)) {
      setErrorMessage('برای این شماره قبلاً کد دعوت ثبت شده است.');
      return;
    }

    setInvitedStudents([...invitedStudents, { 
      phone: normalized, 
      avatar: `https://picsum.photos/seed/${normalized}/40/40`,
      inviteCode: generateStableInviteCode(normalized),
    }]);
    setNewPhone('');
    setErrorMessage(null);
  };

  const handleRemoveStudent = (phone: string) => {
    setInvitedStudents(invitedStudents.filter(s => s.phone !== phone));
  };

  const handleCopyCode = (code: string) => {
    navigator.clipboard.writeText(code);
    setCopiedCode(code);
    setTimeout(() => setCopiedCode(null), 2000);
  };

  return (
    <Card className="border-border/40 rounded-2xl overflow-hidden bg-card/70 backdrop-blur">
      <CardHeader 
        className="cursor-pointer hover:bg-primary/5 transition-colors"
        onClick={onToggle}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
              <Users className="h-5 w-5 text-primary" />
            </div>
            <div>
              <CardTitle className="text-lg">دعوت دانش‌آموزان</CardTitle>
              <p className="text-xs text-muted-foreground mt-0.5">
                {invitedStudents.length} نفر اضافه شده
              </p>
            </div>
          </div>
          <ChevronDown className={cn(
            "h-5 w-5 text-muted-foreground transition-transform duration-200",
            isExpanded && "rotate-180"
          )} />
        </div>
      </CardHeader>
      {isExpanded && (
        <CardContent className="pt-0 space-y-5 text-start">
          {/* افزودن دستی */}
          <div className="space-y-2 text-start">
            <Label>افزودن دستی (شماره تلفن اجباری)</Label>
            <div className="flex flex-col sm:flex-row gap-3">
              <Input 
                value={newPhone}
                onChange={(e) => {
                  setNewPhone(e.target.value);
                  if (errorMessage) setErrorMessage(null);
                }}
                placeholder="شماره تلفن دانش‌آموز (مثلاً 09120000000)" 
                className="h-11 bg-background rounded-xl flex-1 text-start" 
                onKeyDown={(e) => e.key === 'Enter' && handleAddStudent()}
              />
              <Button 
                onClick={handleAddStudent} 
                className="h-11 px-5 bg-primary text-primary-foreground hover:bg-primary/90 rounded-xl w-full sm:w-auto"
              >
                <Plus className="h-4 w-4 me-2" />
                افزودن
              </Button>
            </div>
            {errorMessage ? (
              <p className="text-sm text-destructive flex items-center gap-2">
                {errorMessage}
              </p>
            ) : null}
          </div>

          {/* لیست دانش‌آموزان */}
          {invitedStudents.length > 0 && (
            <div className="space-y-2 text-start">
              <Label>دانش‌آموزان دعوت شده</Label>
              <div className="space-y-2">
                {invitedStudents.map((student, index) => (
                  <div 
                    key={student.phone} 
                    className="flex items-center justify-between p-3 bg-muted/30 rounded-xl group hover:bg-muted/50 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <span className="w-6 h-6 rounded-full bg-muted text-xs flex items-center justify-center text-muted-foreground">
                        {index + 1}
                      </span>
                      <Avatar className="h-9 w-9">
                        <AvatarImage src={student.avatar} />
                        <AvatarFallback>
                          <User className="h-4 w-4" />
                        </AvatarFallback>
                      </Avatar>
                      <div className="flex flex-col">
                        <span className="text-sm font-medium text-foreground">{student.phone}</span>
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                          <code className="px-2 py-1 rounded-md bg-background border border-border/50 font-mono tracking-tight">
                            {student.inviteCode}
                          </code>
                          <Button 
                            variant="ghost" 
                            size="icon" 
                            className="h-8 w-8 text-muted-foreground hover:text-foreground"
                            onClick={() => handleCopyCode(student.inviteCode)}
                          >
                            {copiedCode === student.inviteCode ? (
                              <Check className="h-4 w-4 text-green-500" />
                            ) : (
                              <Copy className="h-4 w-4" />
                            )}
                          </Button>
                        </div>
                      </div>
                    </div>
                    <Button 
                      variant="ghost" 
                      size="icon" 
                      onClick={() => handleRemoveStudent(student.phone)} 
                      className="opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded-lg"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      )}
    </Card>
  );
}