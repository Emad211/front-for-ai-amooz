'use client';

import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useState } from 'react';
import { 
  ArrowRight, 
  Save, 
  Plus, 
  Trash2, 
  GripVertical,
  Video,
  FileText,
  HelpCircle,
  ClipboardList,
  ChevronDown,
  ChevronUp,
  Image as ImageIcon
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { ErrorState } from '@/components/shared/error-state';
import { useClassDetail } from '@/hooks/use-class-detail';
import { Switch } from '@/components/ui/switch';
import { 
  Select, 
  SelectContent, 
  SelectItem, 
  SelectTrigger, 
  SelectValue 
} from '@/components/ui/select';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { toast } from 'sonner';

const lessonTypeIcon: Record<string, React.ReactNode> = {
  video: <Video className="h-4 w-4" />,
  text: <FileText className="h-4 w-4" />,
  quiz: <HelpCircle className="h-4 w-4" />,
  assignment: <ClipboardList className="h-4 w-4" />,
};

const lessonTypeLabel: Record<string, string> = {
  video: 'ویدیو',
  text: 'متن',
  quiz: 'آزمون',
  assignment: 'تکلیف',
};

export default function ClassEditPage() {
  const params = useParams();
  const router = useRouter();
  const classId = Array.isArray(params?.classId) ? params.classId[0] : params?.classId || '';
  
  const { classDetail, isLoading, error, reload, updateClass, isUpdating } = useClassDetail(classId);
  const [openChapters, setOpenChapters] = useState<string[]>([]);

  const toggleChapter = (chapterId: string) => {
    setOpenChapters(prev => 
      prev.includes(chapterId) 
        ? prev.filter(id => id !== chapterId)
        : [...prev, chapterId]
    );
  };

  const handleSave = async () => {
    try {
      await updateClass({
        title: classDetail?.title,
        description: classDetail?.description,
      });
      toast.success('تغییرات با موفقیت ذخیره شد');
    } catch {
      toast.error('خطا در ذخیره تغییرات');
    }
  };

  if (error) {
    return (
      <div className="flex items-center justify-center h-[60vh] px-4">
        <div className="w-full max-w-2xl">
          <ErrorState title="خطا در دریافت اطلاعات کلاس" description={error} onRetry={reload} />
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-48" />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            <Skeleton className="h-96 rounded-2xl" />
          </div>
          <div className="space-y-6">
            <Skeleton className="h-64 rounded-2xl" />
          </div>
        </div>
      </div>
    );
  }

  if (!classDetail) {
    return (
      <div className="flex items-center justify-center h-[60vh] px-4">
        <div className="w-full max-w-2xl">
          <ErrorState title="کلاس یافت نشد" description="کلاس مورد نظر وجود ندارد یا حذف شده است." />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => router.back()} className="rounded-full">
            <ArrowRight className="h-5 w-5" />
          </Button>
          <div>
            <p className="text-sm text-muted-foreground">ویرایش کلاس</p>
            <h1 className="text-2xl font-bold">{classDetail.title}</h1>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" asChild>
            <Link href={`/admin/my-classes/${classId}`}>انصراف</Link>
          </Button>
          <Button onClick={handleSave} disabled={isUpdating}>
            <Save className="h-4 w-4 ml-2" />
            {isUpdating ? 'در حال ذخیره...' : 'ذخیره تغییرات'}
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Basic Info */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">اطلاعات پایه</CardTitle>
              <CardDescription>عنوان و توضیحات کلاس را ویرایش کنید</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="title">عنوان کلاس</Label>
                <Input 
                  id="title" 
                  defaultValue={classDetail.title} 
                  placeholder="عنوان کلاس را وارد کنید"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="description">توضیحات</Label>
                <Textarea 
                  id="description" 
                  defaultValue={classDetail.description} 
                  placeholder="توضیحات کلاس را وارد کنید"
                  rows={4}
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="category">دسته‌بندی</Label>
                  <Select defaultValue={classDetail.category}>
                    <SelectTrigger>
                      <SelectValue placeholder="انتخاب دسته‌بندی" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="ریاضی">ریاضی</SelectItem>
                      <SelectItem value="فیزیک">فیزیک</SelectItem>
                      <SelectItem value="شیمی">شیمی</SelectItem>
                      <SelectItem value="برنامه‌نویسی">برنامه‌نویسی</SelectItem>
                      <SelectItem value="هوش مصنوعی">هوش مصنوعی</SelectItem>
                      <SelectItem value="زبان">زبان</SelectItem>
                      <SelectItem value="ادبیات">ادبیات</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="level">سطح</Label>
                  <Select defaultValue={classDetail.level}>
                    <SelectTrigger>
                      <SelectValue placeholder="انتخاب سطح" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="مبتدی">مبتدی</SelectItem>
                      <SelectItem value="متوسط">متوسط</SelectItem>
                      <SelectItem value="پیشرفته">پیشرفته</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="instructor">مدرس</Label>
                <Input 
                  id="instructor" 
                  defaultValue={classDetail.instructor} 
                  placeholder="نام مدرس را وارد کنید"
                />
              </div>
            </CardContent>
          </Card>

          {/* Chapters & Lessons */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle className="text-lg">سرفصل‌ها و دروس</CardTitle>
                <CardDescription>محتوای آموزشی کلاس را مدیریت کنید</CardDescription>
              </div>
              <Button variant="outline" size="sm">
                <Plus className="h-4 w-4 ml-2" />
                فصل جدید
              </Button>
            </CardHeader>
            <CardContent className="space-y-4">
              {classDetail.chapters?.map((chapter, index) => (
                <Collapsible 
                  key={chapter.id} 
                  open={openChapters.includes(chapter.id)}
                  onOpenChange={() => toggleChapter(chapter.id)}
                >
                  <div className="border rounded-xl overflow-hidden">
                    <CollapsibleTrigger asChild>
                      <div className="flex items-center justify-between p-4 bg-muted/30 cursor-pointer hover:bg-muted/50 transition-colors">
                        <div className="flex items-center gap-3">
                          <GripVertical className="h-4 w-4 text-muted-foreground cursor-grab" />
                          <span className="font-semibold">فصل {index + 1}: {chapter.title}</span>
                          <Badge variant="secondary" className="text-xs">{chapter.lessons.length} درس</Badge>
                        </div>
                        <div className="flex items-center gap-2">
                          <Button variant="ghost" size="icon" className="h-8 w-8">
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                          {openChapters.includes(chapter.id) ? (
                            <ChevronUp className="h-4 w-4" />
                          ) : (
                            <ChevronDown className="h-4 w-4" />
                          )}
                        </div>
                      </div>
                    </CollapsibleTrigger>
                    <CollapsibleContent>
                      <div className="p-4 space-y-2 border-t">
                        {chapter.lessons.map(lesson => (
                          <div key={lesson.id} className="flex items-center justify-between p-3 rounded-lg bg-background border text-sm group">
                            <div className="flex items-center gap-3">
                              <GripVertical className="h-4 w-4 text-muted-foreground cursor-grab opacity-0 group-hover:opacity-100 transition-opacity" />
                              <span className="text-muted-foreground">{lessonTypeIcon[lesson.type]}</span>
                              <span>{lesson.title}</span>
                              <Badge variant="outline" className="text-[10px]">{lessonTypeLabel[lesson.type]}</Badge>
                            </div>
                            <div className="flex items-center gap-3">
                              <span className="text-xs text-muted-foreground">{lesson.duration}</span>
                              <Switch checked={lesson.isPublished} />
                              <Button variant="ghost" size="icon" className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity">
                                <Trash2 className="h-4 w-4 text-destructive" />
                              </Button>
                            </div>
                          </div>
                        ))}
                        <Button variant="outline" size="sm" className="w-full mt-2 border-dashed">
                          <Plus className="h-4 w-4 ml-2" />
                          افزودن درس
                        </Button>
                      </div>
                    </CollapsibleContent>
                  </div>
                </Collapsible>
              ))}
            </CardContent>
          </Card>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Status */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">وضعیت انتشار</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>وضعیت کلاس</Label>
                <Select defaultValue={classDetail.status}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="draft">پیش‌نویس</SelectItem>
                    <SelectItem value="active">فعال</SelectItem>
                    <SelectItem value="paused">متوقف</SelectItem>
                    <SelectItem value="archived">آرشیو شده</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="flex items-center justify-between">
                <Label htmlFor="visible">نمایش در لیست</Label>
                <Switch id="visible" defaultChecked />
              </div>
              <div className="flex items-center justify-between">
                <Label htmlFor="enrollment">ثبت‌نام باز</Label>
                <Switch id="enrollment" defaultChecked />
              </div>
            </CardContent>
          </Card>

          {/* Cover Image */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">تصویر کاور</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="aspect-video rounded-xl bg-muted border-2 border-dashed border-border flex items-center justify-center cursor-pointer hover:bg-muted/80 transition-colors">
                {classDetail.image ? (
                  <img 
                    src={classDetail.image} 
                    alt={classDetail.title} 
                    className="w-full h-full object-cover rounded-xl"
                  />
                ) : (
                  <div className="flex flex-col items-center gap-2 text-muted-foreground">
                    <ImageIcon className="h-8 w-8" />
                    <span className="text-sm">آپلود تصویر</span>
                  </div>
                )}
              </div>
              <Button variant="outline" size="sm" className="w-full mt-3">
                تغییر تصویر
              </Button>
            </CardContent>
          </Card>

          {/* Tags */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">برچسب‌ها</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2 mb-3">
                {classDetail.tags.map(tag => (
                  <Badge key={tag} variant="secondary" className="rounded-full gap-1">
                    {tag}
                    <button className="hover:text-destructive">×</button>
                  </Badge>
                ))}
              </div>
              <Input placeholder="برچسب جدید..." className="text-sm" />
            </CardContent>
          </Card>

          {/* Danger Zone */}
          <Card className="border-destructive/50">
            <CardHeader>
              <CardTitle className="text-lg text-destructive">منطقه خطر</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground mb-4">
                با حذف کلاس، تمام محتوا و اطلاعات دانش‌آموزان از بین می‌رود.
              </p>
              <Button variant="destructive" className="w-full">
                <Trash2 className="h-4 w-4 ml-2" />
                حذف کلاس
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
