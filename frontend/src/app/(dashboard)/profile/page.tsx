
'use client';

import { AdminHeader as Header } from '@/components/layout/header';
import { ProfileForm } from '@/components/dashboard/profile/profile-form';

export default function ProfilePage() {
  return (
    <div className="bg-background text-foreground min-h-screen">
      <Header />
      <main className="p-4 md:p-8">
        <div className="max-w-4xl mx-auto space-y-8">
          <div>
            <h1 className="text-4xl font-bold text-foreground mb-2">پروفایل کاربری</h1>
            <p className="text-muted-foreground mb-8">اطلاعات حساب کاربری خود را مدیریت کنید.</p>
          </div>

          <ProfileForm />
        </div>
      </main>
    </div>
  );
}
