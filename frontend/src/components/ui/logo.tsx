import Image from 'next/image';
import Link from 'next/link';
import { cn } from '@/lib/utils';

interface LogoProps {
  className?: string;
  href?: string;
  showText?: boolean;
  textClassName?: string;
  imageSize?: 'sm' | 'md' | 'lg';
}

export function Logo({ 
  className, 
  href = "/", 
  showText = true, 
  textClassName,
  imageSize = 'md'
}: LogoProps) {
  const sizeMap = {
    sm: { h: 'h-8', w: 'w-12', scale: 'scale-[1.8]' },
    md: { h: 'h-10', w: 'w-14', scale: 'scale-[2]' },
    lg: { h: 'h-12', w: 'w-16', scale: 'scale-[2.2]' },
  };

  const currentSize = sizeMap[imageSize];

  return (
    <Link href={href} className={cn("flex items-center gap-2 group relative", className)}>
      <div className={cn("relative", currentSize.h, currentSize.w)}>
        <Image
          src="/logo (2).png"
          alt="AI-Amooz logo"
          fill
          sizes="128px"
          className={cn("object-contain transition-all duration-300 origin-center", currentSize.scale)}
          priority
        />
      </div>
      {showText && (
        <span className={cn("text-xl font-bold text-foreground whitespace-nowrap tracking-tighter", textClassName)}>
          AI-Amooz
        </span>
      )}
    </Link>
  );
}
