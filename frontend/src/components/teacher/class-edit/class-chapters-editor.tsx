'use client';

import { useState } from 'react';
import { Plus, GripVertical, Trash2, Edit, ChevronDown, ChevronUp, Video, FileText, HelpCircle, ClipboardList } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogTrigger,
} from '@/components/ui/dialog';
import type { ClassChapter, ClassLesson } from '@/types';

interface ClassChaptersEditorProps {
  chapters: ClassChapter[];
  onChange: (chapters: ClassChapter[]) => void;
}

const lessonTypeIcon: Record<string, React.ReactNode> = {
  video: <Video className="h-4 w-4" />,
  text: <FileText className="h-4 w-4" />,
  quiz: <HelpCircle className="h-4 w-4" />,
  assignment: <ClipboardList className="h-4 w-4" />,
};

const lessonTypes = [
  { value: 'video', label: 'ویدیو', icon: Video },
  { value: 'text', label: 'متن', icon: FileText },
  { value: 'quiz', label: 'آزمون', icon: HelpCircle },
  { value: 'assignment', label: 'تکلیف', icon: ClipboardList },
];

export function ClassChaptersEditor({ chapters, onChange }: ClassChaptersEditorProps) {
  const [expandedChapter, setExpandedChapter] = useState<string | null>(chapters[0]?.id || null);
  const [newChapterTitle, setNewChapterTitle] = useState('');
  const [newLessonData, setNewLessonData] = useState<Partial<ClassLesson>>({
    title: '',
    type: 'video',
    duration: '',
    isPublished: false,
  });
  const [editingLesson, setEditingLesson] = useState<{ chapterId: string; lesson: ClassLesson } | null>(null);

  const addChapter = () => {
    if (!newChapterTitle.trim()) return;
    const newChapter: ClassChapter = {
      id: `ch-${Date.now()}`,
      title: newChapterTitle,
      order: chapters.length + 1,
      lessons: [],
    };
    onChange([...chapters, newChapter]);
    setNewChapterTitle('');
  };

  const deleteChapter = (chapterId: string) => {
    onChange(chapters.filter(ch => ch.id !== chapterId));
  };

  const addLesson = (chapterId: string) => {
    if (!newLessonData.title?.trim()) return;
    const newLesson: ClassLesson = {
      id: `ls-${Date.now()}`,
      title: newLessonData.title || '',
      type: newLessonData.type || 'video',
      duration: newLessonData.duration || '۰ دقیقه',
      isPublished: newLessonData.isPublished || false,
      order: (chapters.find(ch => ch.id === chapterId)?.lessons.length || 0) + 1,
    };
    onChange(chapters.map(ch => 
      ch.id === chapterId 
        ? { ...ch, lessons: [...ch.lessons, newLesson] }
        : ch
    ));
    setNewLessonData({ title: '', type: 'video', duration: '', isPublished: false });
  };

  const deleteLesson = (chapterId: string, lessonId: string) => {
    onChange(chapters.map(ch =>
      ch.id === chapterId
        ? { ...ch, lessons: ch.lessons.filter(l => l.id !== lessonId) }
        : ch
    ));
  };

  const updateLesson = (chapterId: string, lessonId: string, data: Partial<ClassLesson>) => {
    onChange(chapters.map(ch =>
      ch.id === chapterId
        ? { ...ch, lessons: ch.lessons.map(l => l.id === lessonId ? { ...l, ...data } : l) }
        : ch
    ));
  };

  const toggleLessonPublish = (chapterId: string, lessonId: string) => {
    onChange(chapters.map(ch =>
      ch.id === chapterId
        ? { 
            ...ch, 
            lessons: ch.lessons.map(l => 
              l.id === lessonId ? { ...l, isPublished: !l.isPublished } : l
            ) 
          }
        : ch
    ));
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">مدیریت سرفصل‌ها و دروس</CardTitle>
        <CardDescription>فصل‌ها و دروس کلاس را ویرایش کنید</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {chapters.map((chapter, chapterIndex) => (
          <div key={chapter.id} className="border rounded-xl overflow-hidden">
            {/* Chapter Header */}
            <div 
              className="flex items-center justify-between p-4 bg-muted/30 cursor-pointer hover:bg-muted/50 transition-colors"
              onClick={() => setExpandedChapter(expandedChapter === chapter.id ? null : chapter.id)}
            >
              <div className="flex items-center gap-3">
                <GripVertical className="h-4 w-4 text-muted-foreground" />
                <span className="font-semibold">فصل {chapterIndex + 1}: {chapter.title}</span>
                <Badge variant="secondary" className="text-xs">{chapter.lessons.length} درس</Badge>
              </div>
              <div className="flex items-center gap-2">
                <Button 
                  variant="ghost" 
                  size="icon" 
                  className="h-8 w-8"
                  onClick={(e) => { e.stopPropagation(); deleteChapter(chapter.id); }}
                >
                  <Trash2 className="h-4 w-4 text-destructive" />
                </Button>
                {expandedChapter === chapter.id ? (
                  <ChevronUp className="h-4 w-4" />
                ) : (
                  <ChevronDown className="h-4 w-4" />
                )}
              </div>
            </div>

            {/* Chapter Content (Lessons) */}
            {expandedChapter === chapter.id && (
              <div className="p-4 space-y-3">
                {chapter.lessons.map(lesson => (
                  <div 
                    key={lesson.id} 
                    className="flex flex-col sm:flex-row sm:items-center justify-between p-3 rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors gap-3"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <GripVertical className="h-4 w-4 text-muted-foreground shrink-0" />
                      <span className="text-muted-foreground shrink-0">{lessonTypeIcon[lesson.type]}</span>
                      <div className="min-w-0 flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-3">
                        <span className="text-sm font-medium truncate">{lesson.title}</span>
                        <span className="text-[10px] sm:text-xs text-muted-foreground shrink-0">{lesson.duration}</span>
                      </div>
                    </div>
                    <div className="flex items-center justify-between sm:justify-end gap-3">
                      <div className="flex items-center gap-2">
                        <Switch 
                          checked={lesson.isPublished}
                          onCheckedChange={() => toggleLessonPublish(chapter.id, lesson.id)}
                          className="scale-75"
                        />
                        <span className="text-[10px] sm:text-xs text-muted-foreground">
                          {lesson.isPublished ? 'منتشر شده' : 'پیش‌نویس'}
                        </span>
                      </div>
                      <div className="flex items-center gap-1">
                        <Button variant="ghost" size="icon" className="h-8 w-8">
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button 
                          variant="ghost" 
                          size="icon" 
                          className="h-8 w-8"
                          onClick={() => deleteLesson(chapter.id, lesson.id)}
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}

                {/* Add Lesson */}
                <Dialog>
                  <DialogTrigger asChild>
                    <Button variant="outline" size="sm" className="w-full border-dashed">
                      <Plus className="h-4 w-4 ml-2" />
                      افزودن درس جدید
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>افزودن درس جدید</DialogTitle>
                    </DialogHeader>
                    <div className="space-y-4 py-4">
                      <div className="space-y-2">
                        <Label>عنوان درس</Label>
                        <Input
                          value={newLessonData.title}
                          onChange={e => setNewLessonData(prev => ({ ...prev, title: e.target.value }))}
                          placeholder="عنوان درس را وارد کنید"
                        />
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label>نوع درس</Label>
                          <Select
                            value={newLessonData.type}
                            onValueChange={(value: 'video' | 'text' | 'quiz' | 'assignment') => setNewLessonData(prev => ({ ...prev, type: value }))}
                          >
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {lessonTypes.map(type => (
                                <SelectItem key={type.value} value={type.value}>
                                  <div className="flex items-center gap-2">
                                    <type.icon className="h-4 w-4" />
                                    {type.label}
                                  </div>
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="space-y-2">
                          <Label>مدت زمان</Label>
                          <Input
                            value={newLessonData.duration}
                            onChange={e => setNewLessonData(prev => ({ ...prev, duration: e.target.value }))}
                            placeholder="مثال: ۱۵ دقیقه"
                          />
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Switch
                          checked={newLessonData.isPublished}
                          onCheckedChange={checked => setNewLessonData(prev => ({ ...prev, isPublished: checked }))}
                        />
                        <Label>انتشار فوری</Label>
                      </div>
                    </div>
                    <DialogFooter>
                      <Button onClick={() => addLesson(chapter.id)}>افزودن</Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              </div>
            )}
          </div>
        ))}

        {/* Add Chapter */}
        <div className="flex items-center gap-2 pt-4">
          <Input
            value={newChapterTitle}
            onChange={e => setNewChapterTitle(e.target.value)}
            placeholder="عنوان فصل جدید"
            onKeyDown={e => e.key === 'Enter' && addChapter()}
          />
          <Button onClick={addChapter}>
            <Plus className="h-4 w-4 ml-2" />
            افزودن فصل
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
