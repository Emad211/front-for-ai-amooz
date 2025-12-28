'use client';

import { Users, User, Search, Check } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Checkbox } from '@/components/ui/checkbox';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';

interface Student {
  id: string;
  name: string;
  email: string;
  avatar: string;
}

interface RecipientSelectorProps {
  recipientType: 'all' | 'specific';
  onRecipientTypeChange: (type: 'all' | 'specific') => void;
  selectedStudents: string[];
  onSelectStudent: (id: string) => void;
  onSelectAll: (ids: string[]) => void;
  students: Student[];
  searchQuery: string;
  onSearchChange: (query: string) => void;
}

export function RecipientSelector({
  recipientType,
  onRecipientTypeChange,
  selectedStudents,
  onSelectStudent,
  onSelectAll,
  students,
  searchQuery,
  onSearchChange,
}: RecipientSelectorProps) {
  const filteredStudents = students.filter(student => 
    student.name.toLowerCase().includes(searchQuery.toLowerCase()) || 
    student.email.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const allFilteredSelected = filteredStudents.length > 0 && 
    filteredStudents.every(s => selectedStudents.includes(s.id));

  const handleSelectAllFiltered = () => {
    if (allFilteredSelected) {
      // Deselect only the filtered ones
      const filteredIds = filteredStudents.map(s => s.id);
      onSelectAll(selectedStudents.filter(id => !filteredIds.includes(id)));
    } else {
      // Select all filtered ones + keep existing selections
      const newSelected = Array.from(new Set([...selectedStudents, ...filteredStudents.map(s => s.id)]));
      onSelectAll(newSelected);
    }
  };

  return (
    <div className="space-y-6">
      <div className="space-y-4">
        <Label>گیرندگان</Label>
        <RadioGroup 
          value={recipientType} 
          onValueChange={(v) => onRecipientTypeChange(v as 'all' | 'specific')}
          className="grid grid-cols-1 sm:grid-cols-2 gap-4"
        >
          <div 
            className={cn(
              "flex items-center gap-3 border-2 rounded-2xl p-4 cursor-pointer transition-all duration-200 hover:border-primary/50",
              recipientType === 'all' ? "border-primary bg-primary/5 shadow-sm" : "border-border bg-card"
            )}
            onClick={() => onRecipientTypeChange('all')}
          >
            <RadioGroupItem value="all" id="all" className="sr-only" />
            <div className={cn(
              "h-10 w-10 rounded-xl flex items-center justify-center transition-colors",
              recipientType === 'all' ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
            )}>
              <Users className="h-5 w-5" />
            </div>
            <div className="flex-1">
              <Label htmlFor="all" className="cursor-pointer font-bold block">همه دانش‌آموزان</Label>
              <p className="text-[10px] text-muted-foreground">ارسال به تمام کاربران فعال</p>
            </div>
            {recipientType === 'all' && <Check className="h-5 w-5 text-primary" />}
          </div>

          <div 
            className={cn(
              "flex items-center gap-3 border-2 rounded-2xl p-4 cursor-pointer transition-all duration-200 hover:border-primary/50",
              recipientType === 'specific' ? "border-primary bg-primary/5 shadow-sm" : "border-border bg-card"
            )}
            onClick={() => onRecipientTypeChange('specific')}
          >
            <RadioGroupItem value="specific" id="specific" className="sr-only" />
            <div className={cn(
              "h-10 w-10 rounded-xl flex items-center justify-center transition-colors",
              recipientType === 'specific' ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
            )}>
              <User className="h-5 w-5" />
            </div>
            <div className="flex-1">
              <Label htmlFor="specific" className="cursor-pointer font-bold block">انتخاب دانش‌آموزان</Label>
              <p className="text-[10px] text-muted-foreground">انتخاب دستی گیرندگان</p>
            </div>
            {recipientType === 'specific' && <Check className="h-5 w-5 text-primary" />}
          </div>
        </RadioGroup>
      </div>

      {recipientType === 'specific' && (
        <div className="border-2 border-dashed rounded-2xl p-4 space-y-4 bg-muted/30 animate-in fade-in slide-in-from-top-4 duration-300">
          <div className="relative">
            <Search className="absolute start-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input 
              placeholder="جستجوی دانش‌آموز..." 
              value={searchQuery}
              onChange={(e) => onSearchChange(e.target.value)}
              className="bg-background h-12 rounded-xl ps-10 border-none shadow-sm"
            />
          </div>
          
          <div className="flex items-center justify-between text-sm text-muted-foreground px-1">
            <span>{selectedStudents.length} نفر انتخاب شده</span>
            <Button variant="ghost" size="sm" onClick={handleSelectAllFiltered} className="h-auto p-0 hover:bg-transparent text-primary">
              {allFilteredSelected ? 'لغو انتخاب همه' : 'انتخاب همه'}
            </Button>
          </div>

          <ScrollArea className="h-[200px] rounded-lg border bg-background p-2">
            <div className="space-y-2">
              {filteredStudents.map((student) => (
                <div 
                  key={student.id}
                  role="button"
                  tabIndex={0}
                  className="flex items-center gap-3 p-3 rounded-xl hover:bg-secondary/50 transition-colors cursor-pointer"
                  onClick={() => onSelectStudent(student.id)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      onSelectStudent(student.id);
                    }
                  }}
                >
                  <Checkbox 
                    checked={selectedStudents.includes(student.id)}
                    onClick={(e) => e.stopPropagation()}
                    onCheckedChange={() => onSelectStudent(student.id)}
                  />
                  <Avatar className="h-8 w-8">
                    <AvatarImage src={student.avatar} />
                    <AvatarFallback>{student.name[0]}</AvatarFallback>
                  </Avatar>
                  <div className="flex-1">
                    <p className="text-sm font-medium">{student.name}</p>
                    <p className="text-xs text-muted-foreground">{student.email}</p>
                  </div>
                  {selectedStudents.includes(student.id) && (
                    <Check className="h-4 w-4 text-primary animate-in zoom-in duration-200" />
                  )}
                </div>
              ))}
              {filteredStudents.length === 0 && (
                <div className="text-center py-8 text-muted-foreground text-sm">
                  دانش‌آموزی یافت نشد
                </div>
              )}
            </div>
          </ScrollArea>
        </div>
      )}
    </div>
  );
}
