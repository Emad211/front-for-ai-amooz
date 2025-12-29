import { User, Shield, Bell, Settings } from 'lucide-react';

export const PROFILE_TABS = [
  { id: 'personal', label: 'اطلاعات فردی', icon: User },
  { id: 'security', label: 'امنیت حساب', icon: Shield },
  { id: 'notifications', label: 'اطلاع‌رسانی‌ها', icon: Bell },
  { id: 'settings', label: 'تنظیمات عمومی', icon: Settings },
] as const;

export type ProfileTabId = typeof PROFILE_TABS[number]['id'];

export const MOCK_USER_PROFILE = {
  firstName: 'عماد',
  lastName: 'کریمی',
  email: 'emad@example.com',
  phone: '09123456789',
  bio: 'علاقه‌مند به یادگیری ریاضی و برنامه‌نویسی',
  avatar: '/avatars/user.jpg',
};
