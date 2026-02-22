import { TeacherHeader } from "@/components/layout/teacher-header";
import { TeacherSidebar } from "@/components/layout/teacher-sidebar";
import { WorkspaceProvider } from "@/hooks/use-workspace";

export default function TeacherLayout({ children }: { children: React.ReactNode }) {
  return (
    <WorkspaceProvider>
      <div className="flex min-h-screen w-full bg-background" dir="rtl">
        <div className="hidden lg:block">
          <TeacherSidebar />
        </div>
        <div className="flex-1 flex flex-col min-w-0">
          <main className="flex-1 p-4 md:p-6 lg:p-8 overflow-x-hidden">
            <TeacherHeader />
            <div className="mt-6 md:mt-8">
              {children}
            </div>
          </main>
        </div>
      </div>
    </WorkspaceProvider>
  );
}
