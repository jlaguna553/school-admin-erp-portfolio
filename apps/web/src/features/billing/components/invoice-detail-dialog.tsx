'use client';

import { zodResolver } from '@hookform/resolvers/zod';
import { Loader2, Plus } from 'lucide-react';
import { useLocale, useTranslations } from 'next-intl';
import { useMemo, useState } from 'react';
import { useForm } from 'react-hook-form';
import { toast } from 'sonner';
import { z } from 'zod';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { FormField, describedBy } from '@/components/ui/form-field';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  TableWrapper,
} from '@/components/ui/table';
import { toApiError } from '@/lib/api-client';
import { useTenantCurrency } from '@/features/auth/api/use-tenant-currency';
import { formatCurrency } from '@/lib/utils';

import { useInvoice, useInvoiceEnrollment, useRegisterPayment } from '../api/use-billing';
import { InvoiceStatusBadge } from './invoice-status-badge';

interface InvoiceDetailDialogProps {
  invoiceId: string | null;
  onOpenChange: (open: boolean) => void;
}

export function InvoiceDetailDialog({ invoiceId, onOpenChange }: InvoiceDetailDialogProps) {
  const t = useTranslations('billing');
  const tc = useTranslations('common');
  const locale = useLocale();

  const tenantCurrency = useTenantCurrency();
  const { data: invoice, isPending } = useInvoice(invoiceId);
  const { data: enrollment } = useInvoiceEnrollment(invoiceId);
  const [paying, setPaying] = useState(false);

  const dateFormatter = useMemo(
    () => new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeZone: 'UTC' }),
    [locale],
  );

  // Falls back to the institution's currency, not a fixed code: while the
  // invoice loads there is nothing to read it from, and formatting a Mexican
  // school's amounts as euros for that instant is simply wrong.
  const money = (value: string | number) =>
    formatCurrency(value, invoice?.currency ?? tenantCurrency, locale);

  return (
    <Dialog open={Boolean(invoiceId)} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl" closeLabel={tc('close')}>
        {isPending || !invoice ? (
          <div className="space-y-3">
            <Skeleton className="h-6 w-48" />
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-32 w-full" />
          </div>
        ) : (
          <>
            <DialogHeader>
              <DialogTitle className="flex flex-wrap items-center gap-2">
                <span className="font-mono">{invoice.number}</span>
                <InvoiceStatusBadge status={invoice.status} />
              </DialogTitle>
              <DialogDescription>
                {invoice.student_name_snapshot} · {invoice.program_name_snapshot}
              </DialogDescription>
            </DialogHeader>

            <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
              <div>
                <dt className="text-xs text-muted-foreground">{t('issueDate')}</dt>
                <dd>{dateFormatter.format(new Date(`${invoice.issue_date}T00:00:00Z`))}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">{t('dueDate')}</dt>
                <dd>{dateFormatter.format(new Date(`${invoice.due_date}T00:00:00Z`))}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">{t('paid')}</dt>
                <dd className="tabular">{money(invoice.amount_paid)}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">{t('balance')}</dt>
                <dd className="tabular font-semibold">{money(invoice.balance)}</dd>
              </div>
            </dl>

            {/* Resolved live through the academic service, not a JOIN. */}
            <div className="rounded-md border border-border bg-muted/40 px-3 py-2 text-xs">
              <span className="text-muted-foreground">{t('enrollmentContext')}: </span>
              {enrollment ? (
                <span>
                  {enrollment.program_code} · {enrollment.academic_year_name} ·{' '}
                  {t(`enrollmentStatus.${enrollment.status}`)}
                </span>
              ) : (
                <span className="text-muted-foreground">{t('enrollmentGone')}</span>
              )}
            </div>

            <section className="mt-4">
              <h3 className="mb-2 text-sm font-semibold">{t('lines')}</h3>
              <TableWrapper className="rounded-md border border-border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead scope="col">{t('concept')}</TableHead>
                      <TableHead scope="col" className="text-right">
                        {t('quantity')}
                      </TableHead>
                      <TableHead scope="col" className="text-right">
                        {t('unitPrice')}
                      </TableHead>
                      <TableHead scope="col" className="text-right">
                        {t('lineTotal')}
                      </TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {invoice.lines.map((line) => (
                      <TableRow key={line.id}>
                        <TableCell>{line.description}</TableCell>
                        <TableCell className="tabular text-right">{line.quantity}</TableCell>
                        <TableCell className="tabular text-right">
                          {money(line.unit_price)}
                        </TableCell>
                        <TableCell className="tabular text-right font-medium">
                          {money(line.line_total)}
                        </TableCell>
                      </TableRow>
                    ))}
                    <TableRow>
                      <TableCell colSpan={3} className="text-right text-sm font-medium">
                        {t('subtotal')}
                      </TableCell>
                      <TableCell className="tabular text-right font-semibold">
                        {money(invoice.subtotal)}
                      </TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
              </TableWrapper>
            </section>

            <section className="mt-4">
              <div className="mb-2 flex items-center justify-between">
                <h3 className="text-sm font-semibold">{t('payments')}</h3>
                {Number(invoice.balance) > 0 ? (
                  <Button size="sm" variant="outline" onClick={() => setPaying(true)}>
                    <Plus aria-hidden />
                    {t('registerPayment')}
                  </Button>
                ) : null}
              </div>

              {invoice.payments.length === 0 ? (
                <p className="text-sm text-muted-foreground">{t('noPayments')}</p>
              ) : (
                <TableWrapper className="rounded-md border border-border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead scope="col">{t('date')}</TableHead>
                        <TableHead scope="col">{t('method')}</TableHead>
                        <TableHead scope="col">{t('reference')}</TableHead>
                        <TableHead scope="col" className="text-right">
                          {t('amount')}
                        </TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {invoice.payments.map((payment) => (
                        <TableRow key={payment.id}>
                          <TableCell>
                            {dateFormatter.format(
                              new Date(`${payment.received_on}T00:00:00Z`),
                            )}
                          </TableCell>
                          <TableCell>{t(`methods.${payment.method}`)}</TableCell>
                          <TableCell className="text-muted-foreground">
                            {payment.reference || '—'}
                          </TableCell>
                          <TableCell className="tabular text-right font-medium">
                            {money(payment.amount)}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableWrapper>
              )}
            </section>

            <PaymentDialog
              open={paying}
              onOpenChange={setPaying}
              invoiceId={invoice.id}
              balance={invoice.balance}
              currency={invoice.currency}
            />
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

function makePaymentSchema(t: (key: string) => string, balance: number) {
  return z.object({
    amount: z.coerce
      .number({ invalid_type_error: t('invalidNumber') })
      .positive(t('positiveNumber'))
      // The server enforces this too; failing here saves a round trip and gives
      // the user the limit in their own currency format.
      .max(balance, t('exceedsBalance')),
    method: z.string().min(1, t('required')),
    reference: z.string().max(120).optional(),
    received_on: z.string().optional(),
  });
}

function PaymentDialog({
  open,
  onOpenChange,
  invoiceId,
  balance,
  currency,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  invoiceId: string;
  balance: string;
  currency: string;
}) {
  const t = useTranslations('billing');
  const tc = useTranslations('common');
  const tv = useTranslations('validation');
  const locale = useLocale();

  const register = useRegisterPayment();
  const schema = makePaymentSchema(tv, Number(balance));

  const form = useForm<z.input<typeof schema>, unknown, z.output<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: {
      // `z.coerce.number()` types its *input* as number, so the API's decimal
      // string has to be converted before it reaches the form.
      amount: Number(balance),
      method: 'transfer',
      reference: '',
      received_on: new Date().toISOString().slice(0, 10),
    },
  });

  async function onSubmit(values: z.output<typeof schema>) {
    try {
      await register.mutateAsync({
        invoiceId,
        payload: {
          amount: String(values.amount),
          method: values.method,
          reference: values.reference ?? '',
          received_on: values.received_on,
        },
      });
      toast.success(t('paymentRegistered'));
      onOpenChange(false);
    } catch (error) {
      toast.error(toApiError(error)?.message ?? tc('genericError'));
    }
  }

  const errors = form.formState.errors;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent closeLabel={tc('close')}>
        <DialogHeader>
          <DialogTitle>{t('registerPayment')}</DialogTitle>
          <DialogDescription>
            {t('balanceHint', { amount: formatCurrency(balance, currency, locale) })}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField id="amount" label={t('amount')} error={errors.amount?.message} required>
              <Input
                id="amount"
                type="number"
                step="0.01"
                min="0.01"
                aria-invalid={Boolean(errors.amount)}
                aria-describedby={describedBy('amount', errors.amount?.message)}
                {...form.register('amount')}
              />
            </FormField>

            <FormField id="method" label={t('method')} error={errors.method?.message} required>
              <Select
                value={form.watch('method')}
                onValueChange={(value) => form.setValue('method', value, { shouldDirty: true })}
              >
                <SelectTrigger id="method">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {['cash', 'card', 'transfer', 'cheque'].map((method) => (
                    <SelectItem key={method} value={method}>
                      {t(`methods.${method}`)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FormField>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <FormField id="received_on" label={t('date')}>
              <Input id="received_on" type="date" {...form.register('received_on')} />
            </FormField>
            <FormField id="reference" label={t('reference')}>
              <Input id="reference" {...form.register('reference')} />
            </FormField>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              {tc('cancel')}
            </Button>
            <Button type="submit" disabled={form.formState.isSubmitting}>
              {form.formState.isSubmitting ? (
                <Loader2 className="animate-spin" aria-hidden />
              ) : null}
              {tc('save')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
