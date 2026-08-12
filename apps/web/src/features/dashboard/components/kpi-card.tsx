import { Card } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

interface KpiCardProps {
  label: string;
  value: string;
  /** Muted caption under the value, e.g. "+3 this week". */
  caption?: string;
  /** Colours only the caption; the value always stays in primary ink. */
  tone?: 'neutral' | 'success' | 'warning';
  isLoading?: boolean;
}

/**
 * A stat tile: small label, oversized value, muted caption.
 *
 * No sparkline and no chart — the tile's whole job is one number, so anything
 * else competes with it. The value keeps text ink (never a series colour); only
 * the caption may carry tone, and the tone always accompanies a worded caption
 * rather than standing in for one.
 */
export function KpiCard({
  label,
  value,
  caption,
  tone = 'neutral',
  isLoading = false,
}: KpiCardProps) {
  return (
    <Card className="p-5">
      <p className="text-sm font-medium text-muted-foreground">{label}</p>

      {isLoading ? (
        <Skeleton className="mt-2 h-9 w-20" />
      ) : (
        <p className="tabular mt-1 text-3xl font-bold">{value}</p>
      )}

      {caption ? (
        <p
          className={cn(
            'mt-1 text-xs',
            tone === 'neutral' && 'text-muted-foreground',
            tone === 'success' && 'text-success',
            tone === 'warning' && 'text-warning',
          )}
        >
          {caption}
        </p>
      ) : null}
    </Card>
  );
}
