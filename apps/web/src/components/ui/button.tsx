'use client';

import { Slot } from '@radix-ui/react-slot';
import { tv, type VariantProps } from 'tailwind-variants';
import { forwardRef } from 'react';

import { cn } from '@/lib/utils';

export const buttonVariants = tv({
  base: [
    'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md',
    'text-sm font-medium transition-colors',
    'disabled:pointer-events-none disabled:opacity-50',
    '[&_svg]:size-4 [&_svg]:shrink-0',
  ],
  variants: {
    variant: {
      primary: 'bg-primary text-primary-foreground hover:opacity-90',
      secondary: 'bg-muted text-foreground hover:bg-border',
      outline: 'border border-border bg-card text-foreground hover:bg-muted',
      ghost: 'text-muted-foreground hover:bg-muted hover:text-foreground',
      destructive: 'bg-destructive text-destructive-foreground hover:opacity-90',
      link: 'text-primary underline-offset-4 hover:underline',
    },
    size: {
      sm: 'h-8 px-3 text-xs',
      md: 'h-9 px-4',
      lg: 'h-10 px-6',
      icon: 'size-9',
    },
    full: {
      true: 'w-full',
    },
  },
  defaultVariants: {
    variant: 'primary',
    size: 'md',
  },
});

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  /** Render as the child element (e.g. a Link) instead of a `<button>`. */
  asChild?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, full, asChild = false, ...props }, ref) => {
    const Component = asChild ? Slot : 'button';
    return (
      <Component
        ref={ref}
        className={cn(buttonVariants({ variant, size, full }), className)}
        {...props}
      />
    );
  },
);
Button.displayName = 'Button';
