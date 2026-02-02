import { useState } from 'react';
import { Save, Loader2, Plus, Trash2, HelpCircle, CheckCircle2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Separator } from '@/components/ui/separator';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import type { ExamPrepSessionDetail, ExamPrepData, ExamPrepQuestion } from '@/services/classes-service';

interface ExamEditFormProps {
  examDetail: ExamPrepSessionDetail;
  onSave: (data: Partial<ExamPrepSessionDetail>) => Promise<void>;
  isSaving?: boolean;
}

const levelOptions = [
  { value: 'مبتدی', label: 'مبتدی' },
  { value: 'متوسط', label: 'متوسط' },
  { value: 'پیشرفته', label: 'پیشرفته' },
];

export function ExamEditForm({ examDetail, onSave, isSaving }: ExamEditFormProps) {
  const [formData, setFormData] = useState({
    title: examDetail.title,
    description: examDetail.description,
    level: examDetail.level || 'مبتدی' as const,
    duration: examDetail.duration || '',
  });

  const [examData, setExamData] = useState<ExamPrepData>(
    examDetail.exam_prep_data || {
      exam_prep: { title: examDetail.title, questions: [] },
    }
  );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await onSave({
      title: formData.title,
      description: formData.description,
      level: formData.level,
      duration: formData.duration,
      exam_prep_json: examData,
    });
  };

  const addQuestion = () => {
    const newQuestion: ExamPrepQuestion = {
      question_id: `q-${Date.now()}`,
      question_text_markdown: '',
      options: [
        { label: 'الف', text_markdown: '' },
        { label: 'ب', text_markdown: '' },
        { label: 'ج', text_markdown: '' },
        { label: 'د', text_markdown: '' },
      ],
      correct_option_label: 'الف',
      correct_option_text_markdown: '',
      teacher_solution_markdown: '',
      final_answer_markdown: '',
      confidence: 1.0,
    };

    setExamData((prev) => ({
      ...prev,
      exam_prep: {
        ...prev.exam_prep,
        questions: [...prev.exam_prep.questions, newQuestion],
      },
    }));
  };

  const removeQuestion = (index: number) => {
    setExamData((prev) => ({
      ...prev,
      exam_prep: {
        ...prev.exam_prep,
        questions: prev.exam_prep.questions.filter((_, i) => i !== index),
      },
    }));
  };

  const updateQuestion = (index: number, updates: Partial<ExamPrepQuestion>) => {
    setExamData((prev) => {
      const newQuestions = [...prev.exam_prep.questions];
      newQuestions[index] = { ...newQuestions[index], ...updates };
      
      // Update correct_option_text_markdown if correct_option_label changed
      if ('correct_option_label' in updates || 'options' in updates) {
        const q = newQuestions[index];
        const correctOpt = q.options.find(o => o.label === q.correct_option_label);
        q.correct_option_text_markdown = correctOpt ? correctOpt.text_markdown : null;
      }

      return {
        ...prev,
        exam_prep: {
          ...prev.exam_prep,
          questions: newQuestions,
        },
      };
    });
  };

  const updateOption = (qIndex: number, oIndex: number, text: string) => {
    setExamData((prev) => {
      const newQuestions = [...prev.exam_prep.questions];
      const newOptions = [...newQuestions[qIndex].options];
      newOptions[oIndex] = { ...newOptions[oIndex], text_markdown: text };
      newQuestions[qIndex] = { ...newQuestions[qIndex], options: newOptions };

      // Update correct_option_text_markdown if this was the correct option
      const q = newQuestions[qIndex];
      if (q.correct_option_label === newOptions[oIndex].label) {
        q.correct_option_text_markdown = text;
      }

      return {
        ...prev,
        exam_prep: {
          ...prev.exam_prep,
          questions: newQuestions,
        },
      };
    });
  };

  return (
    <div className="space-y-8 pb-20">
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">اطلاعات کلی</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2">
                <Label htmlFor="title">عنوان آزمون (الزامی)</Label>
                <Input
                  id="title"
                  value={formData.title}
                  onChange={(e) => setFormData((prev) => ({ ...prev, title: e.target.value }))}
                  placeholder="عنوان آزمون را وارد کنید"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="level">سطح (الزامی)</Label>
                <Select
                  value={formData.level}
                  onValueChange={(value: 'مبتدی' | 'متوسط' | 'پیشرفته') =>
                    setFormData((prev) => ({ ...prev, level: value }))
                  }
                >
                  <SelectTrigger>
                    <SelectValue placeholder="انتخاب سطح" />
                  </SelectTrigger>
                  <SelectContent>
                    {levelOptions.map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>
                        {opt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="duration">زمان تقریبی</Label>
                <Input
                  id="duration"
                  value={formData.duration}
                  onChange={(e) => setFormData((prev) => ({ ...prev, duration: e.target.value }))}
                  placeholder="مثلاً ۱ ساعت یا ۳۰ دقیقه"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">توضیحات</Label>
              <Textarea
                id="description"
                value={formData.description}
                onChange={(e) => setFormData((prev) => ({ ...prev, description: e.target.value }))}
                placeholder="توضیحات آزمون را وارد کنید"
                rows={4}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold flex items-center gap-2">
            <HelpCircle className="h-5 w-5 text-primary" />
            سوالات و پاسخ‌ها
          </h2>
          <Button onClick={addQuestion} variant="outline" size="sm" className="gap-2">
            <Plus className="h-4 w-4" />
            افزودن سوال جدید
          </Button>
        </div>

        <Accordion type="multiple" className="space-y-4">
          {examData.exam_prep.questions.map((q, qIndex) => (
            <AccordionItem 
              key={q.question_id || qIndex} 
              value={q.question_id || `q-${qIndex}`}
              className="border border-border/60 rounded-xl bg-card overflow-hidden"
            >
              <div className="relative group/title">
                <AccordionTrigger className="px-4 py-4 hover:bg-muted/30 transition-colors hover:no-underline">
                  <div className="flex items-center gap-3 text-right">
                    <span className="bg-primary/10 text-primary w-6 h-6 rounded-full flex items-center justify-center text-xs shrink-0">
                      {qIndex + 1}
                    </span>
                    <span className="font-bold text-sm truncate max-w-[250px] md:max-w-[500px]">
                      {q.question_text_markdown ? q.question_text_markdown.split('\n')[0] : 'سؤال جدید'}
                    </span>
                  </div>
                </AccordionTrigger>
                
                <Button
                  variant="ghost"
                  size="icon"
                  className="absolute left-12 top-1/2 -translate-y-1/2 text-destructive opacity-0 group-hover/title:opacity-100 transition-opacity z-10"
                  onClick={(e) => {
                    e.stopPropagation();
                    removeQuestion(qIndex);
                  }}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>

              <AccordionContent className="px-4 pt-4 pb-6 space-y-6">
                <div className="space-y-2">
                  <Label>متن اصلی سوال (صورت سوال)</Label>
                  <Textarea
                    value={q.question_text_markdown || ''}
                    onChange={(e) => updateQuestion(qIndex, { question_text_markdown: e.target.value })}
                    placeholder="صورت سوال را به همراه فرمول‌های LaTeX جانمایی کنید"
                    rows={3}
                    className="font-mono text-sm"
                  />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {q.options.map((opt, oIndex) => (
                    <div key={opt.label} className="space-y-1">
                      <div className="flex items-center justify-between">
                        <Label className="text-xs text-muted-foreground">گزینه {opt.label}</Label>
                        {q.correct_option_label === opt.label && (
                          <span className="text-[10px] bg-green-100 text-green-700 px-1.5 rounded-full flex items-center gap-1">
                            <CheckCircle2 className="h-2 w-2" />
                            پاسخ صحیح
                          </span>
                        )}
                      </div>
                      <Input
                        value={opt.text_markdown || ''}
                        onChange={(e) => updateOption(qIndex, oIndex, e.target.value)}
                        placeholder={`متن گزینه ${opt.label}`}
                      />
                    </div>
                  ))}
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-2">
                    <Label>انتخاب گزینه صحیح</Label>
                    <Select
                      value={q.correct_option_label || ''}
                      onValueChange={(val) => updateQuestion(qIndex, { correct_option_label: val })}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="پاسخ صحیح را انتخاب کنید" />
                      </SelectTrigger>
                      <SelectContent>
                        {q.options.map((opt) => (
                          <SelectItem key={opt.label} value={opt.label}>
                            گزینه {opt.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <Label>خروجی نهایی (نتیجه)</Label>
                    <Input
                      value={q.final_answer_markdown || ''}
                      onChange={(e) => updateQuestion(qIndex, { final_answer_markdown: e.target.value })}
                      placeholder="مثلاً: گزینه ب یا x=5"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label>تحلیل و راه حل مدرس (ارتجاعی - قابل تغییر اندازه)</Label>
                  </div>
                  <Textarea
                    value={q.teacher_solution_markdown || ''}
                    onChange={(e) => updateQuestion(qIndex, { teacher_solution_markdown: e.target.value })}
                    placeholder="توضیحات و راه حل تشریحی مدرس را اینجا وارد کنید"
                    rows={6}
                    className="bg-muted/30 resize-y min-h-[150px]"
                  />
                </div>
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>

        {examData.exam_prep.questions.length === 0 && (
          <div className="text-center py-10 bg-muted/20 rounded-lg border-2 border-dashed border-muted">
            <HelpCircle className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
            <p className="text-muted-foreground">هنوز هیچ سوالی برای این آزمون ثبت نشده است.</p>
            <Button onClick={addQuestion} variant="link" className="mt-2">
              ایجاد اولین سوال
            </Button>
          </div>
        )}
      </div>

      <div className="fixed bottom-6 left-6 right-6 flex justify-end z-50">
        <Button onClick={handleSubmit} disabled={isSaving} size="lg" className="shadow-lg px-8">
          {isSaving ? (
            <Loader2 className="h-5 w-5 animate-spin ml-2" />
          ) : (
            <Save className="h-5 w-5 ml-2" />
          )}
          ذخیره تمام تغییرات آزمون
        </Button>
      </div>
    </div>
  );
}
