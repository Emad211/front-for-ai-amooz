import { 
  PlusCircle, 
  FolderOpen, 
  Users, 
  BarChart3, 
  Home,
  BookOpen,
  Target
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
    title: 'مدیریت کلاس‌ها',
    items: [
      { label: 'ایجاد کلاس جدید', href: '/admin/create-class', icon: PlusCircle },
      { label: 'کلاس‌های من', href: '/admin/my-classes', icon: FolderOpen },
      { label: 'دانش‌آموزان', href: '/admin/students', icon: Users },
    ]
  },
  {
    title: 'گزارشات',
    items: [
      { label: 'آمار و تحلیل', href: '/admin/analytics', icon: BarChart3 },
    ]
  },
];
