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
} from 'lucide-react';
import { NavSection, NavItem } from '@/types';

export const LANDING_NAV_LINKS = [
  { href: "#features", label: "ویژگی‌ها" },
  { href: "#how-it-works", label: "نحوه کار" },
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

/** Navigation menu for teachers/admins when in org workspace mode. */
export const ORG_TEACHER_NAV_MENU: NavSection[] = [
  {
    title: 'سازمان',
    items: [
      { label: 'داشبورد سازمان', href: '/teacher', icon: LayoutDashboard },
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
