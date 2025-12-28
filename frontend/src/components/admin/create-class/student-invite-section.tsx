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
  email: string;
  avatar: string;
}

interface StudentInviteSectionProps {
  isExpanded: boolean;
  onToggle: () => void;
}

export function StudentInviteSection({ isExpanded, onToggle }: StudentInviteSectionProps) {
  const [invitedStudents, setInvitedStudents] = useState<Student[]>([
    { email: 'student1@example.com', avatar: 'https://picsum.photos/seed/s1/40/40' },
  ]);
  const [newStudent, setNewStudent] = useState('');
  const [copied, setCopied] = useState(false);

  const inviteCode = 'AI-AMOOZ-2024';

  const handleAddStudent = () => {
    if (newStudent && !invitedStudents.find(s => s.email === newStudent)) {
      setInvitedStudents([...invitedStudents, { 
        email: newStudent, 
        avatar: `https://picsum.photos/seed/${newStudent}/40/40` 
      }]);
      setNewStudent('');
    }
  };

  const handleRemoveStudent = (email: string) => {
    setInvitedStudents(invitedStudents.filter(s => s.email !== email));
  };

  const handleCopyCode = () => {
    navigator.clipboard.writeText(inviteCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Card className="border-border/50 rounded-2xl overflow-hidden">
      <CardHeader 
        className="cursor-pointer hover:bg-muted/30 transition-colors"
        onClick={onToggle}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-green-500/10 flex items-center justify-center">
              <Users className="h-5 w-5 text-green-500" />
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
        <CardContent className="pt-0 space-y-5">
          {/* کد دعوت */}
          <div className="p-4 bg-muted/30 rounded-xl">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <p className="text-sm font-medium text-foreground">کد دعوت کلاس</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  این کد را با دانش‌آموزان به اشتراک بگذارید
                </p>
              </div>
              <div className="flex items-center gap-2 justify-between sm:justify-end">
                <code className="px-3 py-2 bg-background rounded-lg text-sm font-mono font-bold tracking-wider border border-border/50">
                  {inviteCode}
                </code>
                <Button 
                  variant="outline" 
                  size="icon" 
                  className="rounded-lg h-9 w-9 shrink-0"
                  onClick={handleCopyCode}
                >
                  {copied ? (
                    <Check className="h-4 w-4 text-green-500" />
                  ) : (
                    <Copy className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </div>
          </div>

          {/* افزودن دستی */}
          <div className="space-y-2">
            <Label>افزودن دستی</Label>
            <div className="flex flex-col sm:flex-row gap-3">
              <Input 
                value={newStudent}
                onChange={(e) => setNewStudent(e.target.value)}
                placeholder="ایمیل یا شماره تلفن" 
                className="h-11 bg-background rounded-xl flex-1" 
                onKeyDown={(e) => e.key === 'Enter' && handleAddStudent()}
              />
              <Button 
                onClick={handleAddStudent} 
                className="h-11 px-5 bg-primary text-primary-foreground hover:bg-primary/90 rounded-xl w-full sm:w-auto"
              >
                <Plus className="h-4 w-4 ml-2" />
                افزودن
              </Button>
            </div>
          </div>

          {/* لیست دانش‌آموزان */}
          {invitedStudents.length > 0 && (
            <div className="space-y-2">
              <Label>دانش‌آموزان دعوت شده</Label>
              <div className="space-y-2">
                {invitedStudents.map((student, index) => (
                  <div 
                    key={student.email} 
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
                      <span className="text-sm font-medium text-foreground">
                        {student.email}
                      </span>
                    </div>
                    <Button 
                      variant="ghost" 
                      size="icon" 
                      onClick={() => handleRemoveStudent(student.email)} 
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