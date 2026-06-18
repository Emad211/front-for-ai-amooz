import { AuthAutoRedirect } from '@/components/auth/auth-auto-redirect';

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="auth-layout">
      <AuthAutoRedirect />
      {children}
    </div>
  );
}
