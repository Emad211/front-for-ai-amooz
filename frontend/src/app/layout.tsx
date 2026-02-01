import type { Metadata } from 'next';
import '@fontsource/vazirmatn/100.css';
import '@fontsource/vazirmatn/200.css';
import '@fontsource/vazirmatn/300.css';
import '@fontsource/vazirmatn/400.css';
import '@fontsource/vazirmatn/500.css';
import '@fontsource/vazirmatn/600.css';
import '@fontsource/vazirmatn/700.css';
import '@fontsource/vazirmatn/800.css';
import '@fontsource/vazirmatn/900.css';
import 'katex/dist/katex.min.css';
import './globals.css';
import { Toaster } from "@/components/ui/toaster";
import { Toaster as SonnerToaster } from "sonner";
import { ThemeProvider } from "@/components/theme-provider";

export const metadata: Metadata = {
  title: 'AI-Amooz',
  description: 'پلتفرم آموزشی هوشمند برای یادگیری شخصی‌سازی شده.',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="fa" dir="rtl" suppressHydrationWarning>
      <body className="font-body antialiased">
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          enableSystem
          disableTransitionOnChange
        >
          {children}
          <Toaster />
          <SonnerToaster
            position="top-center"
            dir="rtl"
            richColors
            toastOptions={{
              className: 'text-right',
              descriptionClassName: 'text-right',
            }}
          />
        </ThemeProvider>
      </body>
    </html>
  );
}
