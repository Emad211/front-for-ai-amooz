import { 
  BarChart3, 
  Building2,
  Coins,
  Home,
  BookOpen,
  Target,
  MessageSquare,
  Ticket,
  ServerCog,
  HardDriveDownload,
  ShieldCheck,
  Radio,
  PlusCircle,
  FolderOpen,
  Users,
  FileQuestion,
  LayoutDashboard,
  KeyRound,
  ClipboardList,
  UserCog,
} from 'lucide-react';
import { NavSection, NavItem, OrgRole } from '@/types';

export const LANDING_NAV_LINKS = [
  { href: "#features", label: "ویژگی‌ها" },
  { href: "#why-us", label: "نحوه کار" },
  { href: "#faq", label: "سوالات متداول" },
];

export const DASHBOARD_NAV_LINKS: NavItem[] = [
  { label: "خانه", href: "/home", icon: Home },
  { label: "کلاس‌ها", href: "/classes", icon: BookOpen },
  { label: "آمادگی آزمون", href: "/exam-prep", icon: Target },
];

export const ADMIN_NAV_MENU: NavSection[] = [
  {
    title: 'مدیریت سازمان‌ها',
    items: [
      { label: 'سازمان‌ها', href: '/admin/organizations', icon: Building2 },
    ]
  },
  {
    title: 'مدیریت کاربران',
    items: [
      { label: 'کاربران', href: '/admin/users', icon: Users },
      { label: 'درخواست‌های دسترسی', href: '/admin/waitlist', icon: ClipboardList },
    ]
  },
  {
    title: 'ارتباطات',
    items: [
      { label: 'پیام همگانی', href: '/admin/broadcast', icon: Radio },
      { label: 'تیکت‌ها', href: '/admin/tickets', icon: Ticket },
    ]
  },
  {
    title: 'عملیات سرور',
    items: [
      { label: 'نگهداری و سلامت', href: '/admin/maintenance', icon: ShieldCheck },
      { label: 'بک‌آپ‌ها', href: '/admin/backups', icon: HardDriveDownload },
      { label: 'تنظیمات کلی سرور', href: '/admin/server-settings', icon: ServerCog },
    ]
  },
  {
    title: 'گزارشات',
    items: [
      { label: 'آمار و تحلیل', href: '/admin/analytics', icon: BarChart3 },
      { label: 'مصرف توکن LLM', href: '/admin/llm-usage', icon: Coins },
    ]
  },
];

export const TEACHER_NAV_MENU: NavSection[] = [
  {
    title: 'مدیریت کلاس‌ها',
    items: [
      { label: 'ایجاد کلاس جدید', href: '/teacher/create-class', icon: PlusCircle },
      { label: 'کلاس‌های من', href: '/teacher/my-classes', icon: FolderOpen },
      { label: 'آزمون‌های من', href: '/teacher/my-exams', icon: FileQuestion },
      { label: 'دانش‌آموزان', href: '/teacher/students', icon: Users },
    ]
  },
  {
    title: 'ارتباطات و پشتیبانی',
    items: [
      { label: 'ارسال پیام', href: '/teacher/messages', icon: MessageSquare },
      { label: 'تیکت‌های پشتیبانی', href: '/teacher/tickets', icon: Ticket },
    ]
  },
  {
    title: 'گزارشات',
    items: [
      { label: 'آمار و تحلیل', href: '/teacher/analytics', icon: BarChart3 },
    ]
  },
];

/** Navigation menu for org admins/deputies (managers) when in org workspace mode. */
export const ORG_TEACHER_NAV_MENU: NavSection[] = [
  {
    title: 'سازمان',
    items: [
      { label: 'داشبورد سازمان', href: '/teacher', icon: LayoutDashboard },
      { label: 'مدیریت سازمان', href: '/teacher/org', icon: UserCog },
    ]
  },
  {
    title: 'مدیریت کلاس‌ها',
    items: [
      { label: 'ایجاد کلاس جدید', href: '/teacher/create-class', icon: PlusCircle },
      { label: 'کلاس‌های سازمان', href: '/teacher/my-classes', icon: FolderOpen },
      { label: 'آزمون‌های سازمان', href: '/teacher/my-exams', icon: FileQuestion },
      { label: 'دانش‌آموزان', href: '/teacher/students', icon: Users },
    ]
  },
  {
    title: 'ارتباطات و پشتیبانی',
    items: [
      { label: 'ارسال پیام', href: '/teacher/messages', icon: MessageSquare },
      { label: 'تیکت‌های پشتیبانی', href: '/teacher/tickets', icon: Ticket },
    ]
  },
  {
    title: 'گزارشات',
    items: [
      { label: 'آمار و تحلیل', href: '/teacher/analytics', icon: BarChart3 },
    ]
  },
];

/**
 * Org teacher (org_role=teacher) nav: the org menu WITHOUT the management
 * "سازمان" dashboard section (that view is IsOrgAdmin-only). That section is the
 * first entry of ORG_TEACHER_NAV_MENU, so drop it.
 */
export const ORG_TEACHER_TEACHING_NAV_MENU: NavSection[] = ORG_TEACHER_NAV_MENU.slice(1);

/**
 * Org MANAGER nav: management + oversight ONLY. A manager does NOT create content
 * (no "create class"/"create exam" — that is a teacher action). They manage
 * members/groups/codes, oversee all the org's classes, and watch AI costs.
 */
export const ORG_MANAGER_NAV_MENU: NavSection[] = [
  {
    title: 'مدیریت سازمان',
    items: [
      { label: 'داشبورد', href: '/teacher', icon: LayoutDashboard },
      { label: 'اعضا و گروه‌ها', href: '/teacher/org', icon: UserCog },
    ],
  },
  {
    title: 'نظارت',
    items: [
      { label: 'کلاس‌ها', href: '/teacher/org/classes', icon: FolderOpen },
      { label: 'هزینه‌ها', href: '/teacher/org/costs', icon: Coins },
    ],
  },
  {
    title: 'پشتیبانی',
    items: [
      { label: 'تیکت‌های پشتیبانی', href: '/teacher/tickets', icon: Ticket },
    ],
  },
];

/** Pick the teacher sidebar/header nav for the current workspace + org role. */
export function getTeacherNavMenu(
  isOrgMode: boolean,
  orgRole?: OrgRole | null,
): NavSection[] {
  if (!isOrgMode) return TEACHER_NAV_MENU;
  // Managers (org admin/deputy) get a management/oversight-only menu — NO content
  // creation. Org teachers get the teaching menu (they DO create content).
  if (orgRole === 'admin' || orgRole === 'deputy') return ORG_MANAGER_NAV_MENU;
  return ORG_TEACHER_TEACHING_NAV_MENU;
}
