'use client';

import { forwardRef, useState } from 'react';
import { Eye, EyeOff, Lock } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';

export interface PasswordInputProps
  extends React.ComponentPropsWithoutRef<typeof Input> {
  /** Show a lock icon on the (right, RTL) leading edge. */
  withIcon?: boolean;
}

/**
 * Password field with a built-in show/hide toggle — the single source of truth
 * for password UX across every auth form (login, reset, register, code-join).
 * Works with both react-hook-form (`{...register('password')}`) and controlled
 * (`value`/`onChange`) usage because it forwards the ref and spreads props.
 */
export const PasswordInput = forwardRef<HTMLInputElement, PasswordInputProps>(
  function PasswordInput({ className, withIcon = false, disabled, ...props }, ref) {
    const [show, setShow] = useState(false);
    return (
      <div className="relative">
        {withIcon && (
          <Lock className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
        )}
        <Input
          ref={ref}
          type={show ? 'text' : 'password'}
          dir="ltr"
          disabled={disabled}
          className={cn(withIcon && 'pr-10', 'pl-10', className)}
          {...props}
        />
        <button
          type="button"
          onClick={() => setShow((s) => !s)}
          disabled={disabled}
          aria-label={show ? 'پنهان کردن رمز عبور' : 'نمایش رمز عبور'}
          className="absolute left-1 top-1/2 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
        >
          {show ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
        </button>
      </div>
    );
  },
);
