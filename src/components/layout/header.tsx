'use client';

import Link from 'next/link';
import { GraduationCap } from 'lucide-react';

const Logo = () => (
  <Link href="/" className="flex items-center gap-2">
    <GraduationCap className="h-7 w-7 text-primary" />
    <span className="text-xl font-bold text-text-light">AI-Amooz</span>
  </Link>
);

export function Header() {
  return (
    <header className="flex items-center justify-center p-4 border-b border-border">
      <Logo />
    </header>
  );
}
