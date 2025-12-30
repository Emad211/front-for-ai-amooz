import { Bell, Settings, Shield, User } from 'lucide-react';

export const PROFILE_TABS = [
  { id: 'personal', label: 'اطلاعات فردی', icon: User },
  { id: 'security', label: 'امنیت حساب', icon: Shield },
  { id: 'notifications', label: 'اطلاع‌رسانی‌ها', icon: Bell },
  { id: 'settings', label: 'تنظیمات عمومی', icon: Settings },
] as const;

export type ProfileTabId = (typeof PROFILE_TABS)[number]['id'];
