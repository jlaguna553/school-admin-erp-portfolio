import { tv, type VariantProps } from 'tailwind-variants';

import { cn } from '@/lib/utils';

/**
 * Status pill.
 *
 * Status colours are reserved for state and are never reused as chart series
 * colours. Each variant pairs its colour with a text label (and callers add an
 * icon where space allows), so state is never communicated by colour alone.
 */
export const badgeVariants = tv({
  base: 'inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium',
  variants: {
    variant: {
      neutral: 'bg-muted text-muted-foreground',
      success: 'bg-success/10 text-success',
      warning: 'bg-warning/10 text-warning',
      info: 'bg-info/10 text-info',
      destructive: 'bg-destructive/10 text-destructive',
      outline: 'border border-border text-muted-foreground',
    },
  },
  defaultVariants: {
    variant: 'neutral',
  },
});

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}
