'use client';

import { Users, User, Search, Check } from 'lucide-react';
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
          className="flex flex-col sm:flex-row gap-4"
        >
          <div className="flex items-center gap-3 border rounded-xl p-4 min-h-12 flex-1 cursor-pointer hover:bg-secondary/50 transition-colors [&:has(:checked)]:border-primary [&:has(:checked)]:bg-primary/5">
            <RadioGroupItem value="all" id="all" />
            <Label htmlFor="all" className="cursor-pointer flex-1">همه دانش‌آموزان</Label>
            <Users className="h-4 w-4 text-muted-foreground" />
          </div>
          <div className="flex items-center gap-3 border rounded-xl p-4 min-h-12 flex-1 cursor-pointer hover:bg-secondary/50 transition-colors [&:has(:checked)]:border-primary [&:has(:checked)]:bg-primary/5">
            <RadioGroupItem value="specific" id="specific" />
            <Label htmlFor="specific" className="cursor-pointer flex-1">انتخاب دانش‌آموزان</Label>
            <User className="h-4 w-4 text-muted-foreground" />
          </div>
        </RadioGroup>
      </div>

      {recipientType === 'specific' && (
        <div className="border rounded-xl p-4 space-y-4 bg-secondary/20 animate-in fade-in slide-in-from-top-4 duration-300">
          <div className="flex items-center gap-2">
            <Search className="h-4 w-4 text-muted-foreground" />
            <Input 
              placeholder="جستجوی دانش‌آموز..." 
              value={searchQuery}
              onChange={(e) => onSearchChange(e.target.value)}
              className="bg-background h-11 rounded-xl"
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
