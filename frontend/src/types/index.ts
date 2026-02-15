export interface Course {
  id: string | number;
  title: string;
  description: string;
  tags: string[];
  instructor?: string;
  progress?: number;
  image?: string;
  studentsCount?: number;
  lessonsCount?: number;
  status?: 'active' | 'draft' | 'archived' | 'paused';
  createdAt?: string;
  lastActivity?: string;
  category?: string;
  level?: 'مبتدی' | 'متوسط' | 'پیشرفته';
  duration?: string;
  rating?: number;
  reviews?: number;
}

export interface Exam {
  id: string | number;
  title: string;
  description: string;
  tags: string[];
  questions: number;
  subject?: string;
  totalQuestions?: number;
  currentQuestionIndex?: number;
  questionsList?: Question[];
  timeRemaining?: number; // in seconds
}

export interface Question {
  id: string;
  number: number;
  text: string;
  type?: 'multiple_choice' | 'true_false' | 'fill_blank' | 'short_answer';
  options: {
    id: string;
    label: string;
    text: string;
  }[];
  correctOptionId?: string;
  userAnswerId?: string;
}

export interface Lesson {
  id: string;
  title: string;
  type?: 'video' | 'text' | 'quiz';
  duration?: string;
  isActive?: boolean;
  isCompleted?: boolean;
  isLocked?: boolean;
  isSpecial?: boolean;
  content?: string;
  formulas?: { label: string; formula: string }[];
  tips?: string[];

  // Used for chapter-end quiz pseudo-lessons in Learn UI.
  chapterId?: string;

  // Used for course final exam pseudo-lesson in Learn UI.
  finalExam?: boolean;
}

export interface Chapter {
  id: string;
  title: string;
  lessons: Lesson[];
}

export interface Prerequisite {
  id: number;
  order: number;
  name: string;
  teaching_text: string;
}

export interface CourseContent {
  id: string;
  title: string;
  description: string;
  progress: number;
  level: string;
  duration: string;
  recapMarkdown?: string;
  learningObjectives?: string[];
  prerequisites?: Prerequisite[];
  chapters: Chapter[];
}

export interface Activity {
  title: string;
  time: string;
  type: string;
  icon: React.ReactNode;
}

export interface Event {
  title: string;
  status: string;
  date: string;
  month: string;
  icon: React.ReactNode;
}

export interface Student {
  id: string;
  name: string;
  email: string;
  phone: string;
  inviteCode?: string;
  avatar: string;
  enrolledClasses: number;
  completedLessons: number;
  totalLessons: number;
  averageScore: number;
  status: 'active' | 'inactive';
  joinDate: string;
  lastActivity: string;
  performance: 'excellent' | 'good' | 'needs-improvement';
}

export interface NavItem {
  label: string;
  href: string;
  icon?: any;
}

export interface NavSection {
  title: string;
  items: NavItem[];
}

export interface MessageRecipient {
  id: string;
  name: string;
  email: string;
  avatar?: string;
  role?: 'student' | 'teacher';
}

export interface UserProfile {
  id: string;
  username: string;
  name: string;
  email: string;
  phone: string;
  avatar: string;
  role: 'student' | 'admin' | 'teacher';
  grade?: string;
  major?: string;
  bio?: string;
  location?: string;
  joinDate: string;
  isVerified: boolean;
}

export type TicketStatus = 'open' | 'pending' | 'answered' | 'closed';
export type TicketPriority = 'low' | 'medium' | 'high';

export interface TicketMessage {
  id: string;
  content: string;
  isAdmin: boolean;
  createdAt: string;
  attachments?: string[];
}

export interface Ticket {
  id: string;
  subject: string;
  status: TicketStatus;
  priority: TicketPriority;
  department: string;
  createdAt: string;
  updatedAt: string;
  messages: TicketMessage[];
  userId?: string;
  userName?: string;
  userEmail?: string;
}

export type NotificationType = 'info' | 'success' | 'warning' | 'error' | 'message' | 'alert';

export interface Notification {
  id: string;
  title: string;
  message: string;
  type: NotificationType;
  isRead: boolean;
  createdAt: string;
  time?: string;
  link?: string;
}

export interface DashboardStats {
  activeCourses: number;
  totalCourses: number;
  completionPercent: number;
  averageScore: number;
  studyHours: string;
  studyMinutes: string;
}

export interface DashboardActivity {
  id: string;
  title: string;
  time: string;
  type: 'در حال انجام' | 'ویدیو' | 'آزمون' | 'تکلیف';
  icon: 'file' | 'video' | 'book' | 'pen';
}

export interface DashboardEvent {
  id: string;
  title: string;
  status: string;
  date: string;
  month: string;
  icon: 'clock' | 'file';
}

export interface AdminAnalyticsStat {
  title: string;
  value: string;
  change: string;
  trend: 'up' | 'down';
  icon: string;
}

export interface AdminRecentActivity {
  id: number;
  type: string;
  user: string;
  action: string;
  time: string;
  icon: string;
  color: string;
  bg: string;
}

export interface AdminChartData {
  name: string;
  students: number;
}

export interface AdminDistributionData {
  name: string;
  value: number;
}

export type EventType = 'exam' | 'assignment' | 'class' | 'holiday' | 'reminder';
export type EventPriority = 'high' | 'medium' | 'low';

export interface CalendarEvent {
  id: string;
  title: string;
  description?: string;
  date: string; // Format: YYYY-MM-DD (Jalali)
  time?: string; // Format: HH:MM
  endTime?: string;
  type: EventType;
  priority: EventPriority;
  subject?: string;
  location?: string;
  isCompleted?: boolean;
}

export interface CalendarDay {
  day: number;
  isCurrentMonth: boolean;
  isToday: boolean;
  isWeekend: boolean;
  events: CalendarEvent[];
}

export interface AdminProfileSettings {
  name: string;
  email: string;
  phone: string;
  bio: string;
  location: string;
  avatar: string;
}

export interface AdminSecuritySettings {
  twoFactorEnabled: boolean;
  lastPasswordChange: string;
}

export interface AdminNotificationSettings {
  emailNotifications: boolean;
  browserNotifications: boolean;
  smsNotifications: boolean;
  marketingEmails: boolean;
}

// ============================================================================
// Class Detail Types - تایپ‌های جزئیات کلاس
// ============================================================================

export interface ClassStudent {
  id: string;
  name: string;
  email: string;
  avatar: string;
  joinDate: string;
  progress: number;
  lastActivity: string;
  status: 'active' | 'inactive';
  grade?: number;
}

export interface ClassLesson {
  id: string;
  title: string;
  type: 'video' | 'text' | 'quiz' | 'assignment';
  duration: string;
  order: number;
  isPublished: boolean;

  // Optional rich content (derived from Step 2 structure_json units)
  contentMarkdown?: string;
}

export interface ClassChapter {
  id: string;
  title: string;
  order: number;
  lessons: ClassLesson[];
}

export interface ClassDetail extends Course {
  chapters?: ClassChapter[];
  enrolledStudents?: ClassStudent[];
  announcements?: { id: string; title: string; content: string; createdAt: string }[];
  schedule?: { day: string; time: string }[];

  // Derived from `structureJson` (Step 2)
  objectives?: string[];

  // Class creation pipeline outputs (backed by ClassCreationSession)
  pipelineStatus?: string;
  transcriptMarkdown?: string;
  structureJson?: string;
  pipelineErrorDetail?: string;
}
