import { AlertTriangle, Ban, Check, CircleDashed, Clock, FileText } from 'lucide-react';
import { useTranslations } from 'next-intl';

import { Badge, type BadgeProps } from '@/components/ui/badge';

type Variant = NonNullable<BadgeProps['variant']>;

/**
 * Invoice status, always as colour **plus** an icon and a word.
 *
 * "Overdue" in particular must never be communicated by colour alone — it is
 * the one state an accountant scans for.
 */
const presentation: Record<string, { variant: Variant; Icon: typeof Check }> = {
  draft: { variant: 'neutral', Icon: FileText },
  issued: { variant: 'info', Icon: CircleDashed },
  partially_paid: { variant: 'warning', Icon: Clock },
  paid: { variant: 'success', Icon: Check },
  overdue: { variant: 'destructive', Icon: AlertTriangle },
  cancelled: { variant: 'neutral', Icon: Ban },
};

export function InvoiceStatusBadge({ status }: { status: string }) {
  const t = useTranslations('billing');
  const { variant, Icon } = presentation[status] ?? {
    variant: 'neutral' as Variant,
    Icon: FileText,
  };

  return (
    <Badge variant={variant}>
      <Icon className="size-3" aria-hidden />
      {t(`status.${status}`)}
    </Badge>
  );
}
