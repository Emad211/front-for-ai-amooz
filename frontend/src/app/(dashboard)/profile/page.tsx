
'use client';

import { ProfileForm } from '@/components/dashboard/profile/profile-form';
import { Settings } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useProfile } from '@/hooks/use-profile';

export default function ProfilePage() {
  const { activeTab, setActiveTab, tabs, user, updateProfile, isLoading, error } = useProfile();

  return (
    <div className="min-h-screen bg-background/50">
      <main className="container max-w-6xl mx-auto px-4 py-8 md:py-12">
        <div className="flex flex-col gap-8">
          {/* Header Section */}
          <div className="flex flex-col gap-2">
            <h1 className="text-3xl md:text-4xl font-bold tracking-tight">تنظیمات حساب کاربری</h1>
            <p className="text-muted-foreground text-lg">
              اطلاعات شخصی و تنظیمات امنیتی خود را در این بخش مدیریت کنید.
            </p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
            {/* Sidebar Navigation */}
            <aside className="lg:col-span-3">
              <nav className="flex lg:flex-col gap-1 overflow-x-auto pb-2 lg:pb-0 no-scrollbar">
                {tabs.map((tab) => {
                  const Icon = tab.icon;
                  return (
                    <button
                      key={tab.id}
                      onClick={() => setActiveTab(tab.id)}
                      className={cn(
                        "flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all shrink-0",
                        activeTab === tab.id
                          ? "bg-primary text-primary-foreground shadow-lg shadow-primary/20"
                          : "text-muted-foreground hover:bg-muted hover:text-foreground"
                      )}
                    >
                      <Icon className="w-4 h-4" />
                      {tab.label}
                    </button>
                  );
                })}
              </nav>
            </aside>

            {/* Content Area */}
            <div className="lg:col-span-9">
              {activeTab === 'personal' && (
                <ProfileForm
                  user={user}
                  isLoading={isLoading}
                  error={error}
                  onSave={updateProfile}
                />
              )}
              {activeTab !== 'personal' && (
                <div className="bg-card border rounded-3xl p-12 flex flex-col items-center justify-center text-center gap-4 min-h-[400px]">
                  <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center">
                    <Settings className="w-8 h-8 text-muted-foreground" />
                  </div>
                  <div>
                    <h3 className="text-xl font-semibold">این بخش به زودی اضافه می‌شود</h3>
                    <p className="text-muted-foreground mt-1">
                      در حال حاضر فقط بخش اطلاعات شخصی فعال است.
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
