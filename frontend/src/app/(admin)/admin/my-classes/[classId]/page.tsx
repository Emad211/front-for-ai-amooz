'use client';

import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { 
  ArrowRight, 
  Users, 
  BookOpen, 
  Star, 
  Calendar, 
  Clock, 
  Edit, 
  Trash2, 
  UserPlus,
  Play,
  FileText,
  Video,
  HelpCircle,
  ClipboardList
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Skeleton } from '@/components/ui/skeleton';
import { ErrorState } from '@/components/shared/error-state';
import { useClassDetail } from '@/hooks/use-class-detail';
import { Progress } from '@/components/ui/progress';
import { Separator } from '@/components/ui/separator';

const statusConfig: Record<string, { label: string; color: string }> = {
  active: { label: 'فعال', color: 'bg-emerald-500/10 text-emerald-600 border-emerald-500/20' },
  draft: { label: 'پیش‌نویس', color: 'bg-amber-500/10 text-amber-600 border-amber-500/20' },
  paused: { label: 'متوقف', color: 'bg-slate-500/10 text-slate-600 border-slate-500/20' },
  archived: { label: 'آرشیو شده', color: 'bg-red-500/10 text-red-600 border-red-500/20' },
};

const lessonTypeIcon: Record<string, React.ReactNode> = {
  video: <Video className="h-4 w-4" />,
  text: <FileText className="h-4 w-4" />,
  quiz: <HelpCircle className="h-4 w-4" />,
  assignment: <ClipboardList className="h-4 w-4" />,
};

export default function ClassDetailPage() {
  const params = useParams();
  const router = useRouter();
  const classId = Array.isArray(params?.classId) ? params.classId[0] : params?.classId || '';
  
  const { classDetail, students, isLoading, error, reload } = useClassDetail(classId);

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
            <Skeleton className="h-64 rounded-2xl" />
            <Skeleton className="h-48 rounded-2xl" />
          </div>
          <div className="space-y-6">
            <Skeleton className="h-48 rounded-2xl" />
            <Skeleton className="h-32 rounded-2xl" />
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

  const totalLessons = classDetail.chapters?.reduce((acc, ch) => acc + ch.lessons.length, 0) || 0;
  const publishedLessons = classDetail.chapters?.reduce((acc, ch) => acc + ch.lessons.filter(l => l.isPublished).length, 0) || 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => router.back()} className="rounded-full">
            <ArrowRight className="h-5 w-5" />
          </Button>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Badge variant="outline" className={`${statusConfig[classDetail.status || 'draft']?.color}`}>
                {statusConfig[classDetail.status || 'draft']?.label}
              </Badge>
              <Badge variant="outline">{classDetail.level}</Badge>
              <Badge variant="secondary">{classDetail.category}</Badge>
            </div>
            <h1 className="text-2xl font-bold">{classDetail.title}</h1>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" asChild>
            <Link href={`/admin/my-classes/${classId}/students`}>
              <Users className="h-4 w-4 ml-2" />
              مدیریت دانش‌آموزان
            </Link>
          </Button>
          <Button asChild>
            <Link href={`/admin/my-classes/${classId}/edit`}>
              <Edit className="h-4 w-4 ml-2" />
              ویرایش محتوا
            </Link>
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Description Card */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">درباره کلاس</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-muted-foreground leading-relaxed">{classDetail.description}</p>
              <div className="flex flex-wrap gap-2 mt-4">
                {classDetail.tags.map(tag => (
                  <Badge key={tag} variant="secondary" className="rounded-full">{tag}</Badge>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Chapters & Lessons */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle className="text-lg">سرفصل‌ها و دروس</CardTitle>
                <CardDescription>{publishedLessons} از {totalLessons} درس منتشر شده</CardDescription>
              </div>
              <Button variant="outline" size="sm" asChild>
                <Link href={`/admin/my-classes/${classId}/edit`}>
                  <Edit className="h-4 w-4 ml-2" />
                  ویرایش
                </Link>
              </Button>
            </CardHeader>
            <CardContent className="space-y-4">
              {classDetail.chapters?.map((chapter, index) => (
                <div key={chapter.id} className="border rounded-xl p-4">
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="font-semibold">فصل {index + 1}: {chapter.title}</h4>
                    <span className="text-xs text-muted-foreground">{chapter.lessons.length} درس</span>
                  </div>
                  <div className="space-y-2">
                    {chapter.lessons.map(lesson => (
                      <div key={lesson.id} className="flex items-center justify-between p-2 rounded-lg bg-muted/50 text-sm">
                        <div className="flex items-center gap-2">
                          <span className="text-muted-foreground">{lessonTypeIcon[lesson.type]}</span>
                          <span>{lesson.title}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-muted-foreground">{lesson.duration}</span>
                          {lesson.isPublished ? (
                            <Badge variant="outline" className="text-[10px] bg-emerald-500/10 text-emerald-600">منتشر شده</Badge>
                          ) : (
                            <Badge variant="outline" className="text-[10px]">پیش‌نویس</Badge>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>

          {/* Recent Students */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-lg">دانش‌آموزان اخیر</CardTitle>
              <Button variant="link" size="sm" asChild className="text-primary">
                <Link href={`/admin/my-classes/${classId}/students`}>مشاهده همه</Link>
              </Button>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {students.slice(0, 5).map(student => (
                  <div key={student.id} className="flex items-center justify-between p-3 rounded-xl bg-muted/30">
                    <div className="flex items-center gap-3">
                      <Avatar className="h-10 w-10">
                        <AvatarImage src={student.avatar} alt={student.name} />
                        <AvatarFallback>{student.name.charAt(0)}</AvatarFallback>
                      </Avatar>
                      <div>
                        <p className="font-medium text-sm">{student.name}</p>
                        <p className="text-xs text-muted-foreground">{student.email}</p>
                      </div>
                    </div>
                    <div className="text-left">
                      <p className="text-sm font-medium">{student.progress}%</p>
                      <Progress value={student.progress} className="h-1 w-16" />
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Stats Card */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">آمار کلاس</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Users className="h-4 w-4" />
                  <span className="text-sm">دانش‌آموزان</span>
                </div>
                <span className="font-bold">{classDetail.studentsCount}</span>
              </div>
              <Separator />
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-muted-foreground">
                  <BookOpen className="h-4 w-4" />
                  <span className="text-sm">تعداد دروس</span>
                </div>
                <span className="font-bold">{totalLessons}</span>
              </div>
              <Separator />
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Star className="h-4 w-4 text-amber-500" />
                  <span className="text-sm">امتیاز</span>
                </div>
                <span className="font-bold">{classDetail.rating} از ۵</span>
              </div>
              <Separator />
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Calendar className="h-4 w-4" />
                  <span className="text-sm">تاریخ ایجاد</span>
                </div>
                <span className="font-bold text-sm">{classDetail.createdAt}</span>
              </div>
            </CardContent>
          </Card>

          {/* Instructor */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">مدرس</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-3">
                <Avatar className="h-12 w-12">
                  <AvatarImage src={`https://picsum.photos/seed/${classDetail.instructor}/100/100`} />
                  <AvatarFallback>{classDetail.instructor?.charAt(0)}</AvatarFallback>
                </Avatar>
                <div>
                  <p className="font-medium">{classDetail.instructor}</p>
                  <p className="text-xs text-muted-foreground">مدرس دوره</p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Schedule */}
          {classDetail.schedule && classDetail.schedule.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">برنامه کلاس</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {classDetail.schedule.map((item, i) => (
                  <div key={i} className="flex items-center justify-between p-2 rounded-lg bg-muted/50 text-sm">
                    <span className="font-medium">{item.day}</span>
                    <span className="text-muted-foreground">{item.time}</span>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {/* Announcements */}
          {classDetail.announcements && classDetail.announcements.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">اطلاعیه‌ها</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {classDetail.announcements.map(ann => (
                  <div key={ann.id} className="p-3 rounded-lg bg-muted/50">
                    <p className="font-medium text-sm">{ann.title}</p>
                    <p className="text-xs text-muted-foreground mt-1">{ann.content}</p>
                    <p className="text-[10px] text-muted-foreground mt-2">{ann.createdAt}</p>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
