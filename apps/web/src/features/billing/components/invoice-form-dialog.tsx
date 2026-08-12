'use client';

import { zodResolver } from '@hookform/resolvers/zod';
import { Loader2, Plus, Trash2 } from 'lucide-react';
import { useLocale, useTranslations } from 'next-intl';
import { useEffect, useMemo } from 'react';
import { useFieldArray, useForm } from 'react-hook-form';
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
import { useTenantCurrency } from '@/features/auth/api/use-tenant-currency';
import { toApiError, toFieldErrors } from '@/lib/api-client';
import { formatCurrency } from '@/lib/utils';

import { useBillableEnrollments, useCreateInvoice } from '../api/use-billing';

function makeInvoiceSchema(t: (key: string) => string) {
  const decimal = (message: string) =>
    z.string().regex(/^\d+(\.\d{1,2})?$/, message);

  return z.object({
    enrollment_id: z.string().min(1, t('required')),
    issue_date: z.string().min(1, t('required')),
    due_date: z.string().optional().or(z.literal('')),
    notes: z.string().optional().or(z.literal('')),
    lines: z
      .array(
        z.object({
          description: z.string().min(1, t('required')).max(300),
          quantity: decimal(t('invalidNumber')),
          unit_price: decimal(t('invalidNumber')),
        }),
      )
      .min(1, t('required')),
  });
}

type InvoiceFormValues = z.infer<ReturnType<typeof makeInvoiceSchema>>;

const EMPTY_LINE = { description: '', quantity: '1', unit_price: '' };

interface InvoiceFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * Issue an invoice against an enrollment.
 *
 * The currency is shown but never chosen: the institution's setting decides it,
 * so a school cannot end up with two invoices for the same student in different
 * currencies and no exchange rate to reconcile them. The request omits the
 * field entirely and the server denominates it.
 *
 * Amounts are typed as strings all the way to the API. Parsing them into
 * JavaScript numbers would round money at the client -- `0.1 + 0.2` is the
 * canonical example -- while Django stores `DecimalField`.
 */
export function InvoiceFormDialog({ open, onOpenChange }: InvoiceFormDialogProps) {
  const t = useTranslations('billing');
  const tc = useTranslations('common');
  const tv = useTranslations('validation');
  const locale = useLocale();

  const currency = useTenantCurrency();
  const createMutation = useCreateInvoice();
  const { data: enrollments = [], isPending: loadingEnrollments } = useBillableEnrollments();

  const form = useForm<InvoiceFormValues>({
    resolver: zodResolver(makeInvoiceSchema(tv)),
    defaultValues: {
      enrollment_id: '',
      issue_date: new Date().toISOString().slice(0, 10),
      due_date: '',
      notes: '',
      lines: [{ ...EMPTY_LINE }],
    },
  });

  const lines = useFieldArray({ control: form.control, name: 'lines' });

  useEffect(() => {
    if (!open) return;
    form.reset({
      enrollment_id: '',
      issue_date: new Date().toISOString().slice(0, 10),
      due_date: '',
      notes: '',
      lines: [{ ...EMPTY_LINE }],
    });
  }, [open, form]);

  // Preview only. The server recomputes every total from the lines it stores,
  // so this can never be the number of record.
  const watchedLines = form.watch('lines');
  const subtotal = useMemo(
    () =>
      watchedLines.reduce((total, line) => {
        const quantity = Number(line.quantity);
        const price = Number(line.unit_price);
        if (!Number.isFinite(quantity) || !Number.isFinite(price)) return total;
        return total + quantity * price;
      }, 0),
    [watchedLines],
  );

  async function onSubmit(values: InvoiceFormValues) {
    try {
      const invoice = await createMutation.mutateAsync({
        enrollment_id: values.enrollment_id,
        issue_date: values.issue_date,
        // Omitted rather than sent empty: the API defaults it to 30 days out.
        ...(values.due_date ? { due_date: values.due_date } : {}),
        ...(values.notes ? { notes: values.notes } : {}),
        lines: values.lines,
      });
      toast.success(t('invoiceCreated', { number: invoice.number }));
      onOpenChange(false);
    } catch (error) {
      const fieldErrors = toFieldErrors(error);
      let matched = false;
      for (const [field, message] of Object.entries(fieldErrors)) {
        if (field in values) {
          form.setError(field as keyof InvoiceFormValues, { message });
          matched = true;
        }
      }
      // A rejected enrollment comes back as a business-rule violation, not a
      // field error -- it is the service layer, not the serializer, that knows
      // whether an enrollment is billable.
      if (!matched) toast.error(toApiError(error)?.message ?? tc('genericError'));
    }
  }

  const errors = form.formState.errors;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl" closeLabel={tc('cancel')}>
        <DialogHeader>
          <DialogTitle>{t('newInvoice')}</DialogTitle>
          <DialogDescription>
            {t('newInvoiceHint', { currency })}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <FormField
            id="enrollment_id"
            label={t('enrollment')}
            error={errors.enrollment_id?.message}
            hint={t('enrollmentHint')}
            required
          >
            <Select
              value={form.watch('enrollment_id')}
              onValueChange={(value) =>
                form.setValue('enrollment_id', value, { shouldDirty: true })
              }
            >
              <SelectTrigger id="enrollment_id">
                <SelectValue
                  placeholder={loadingEnrollments ? tc('loading') : t('selectEnrollment')}
                />
              </SelectTrigger>
              <SelectContent>
                {enrollments.map((enrollment) => (
                  <SelectItem key={enrollment.id} value={enrollment.id}>
                    {enrollment.student_name} · {enrollment.program_name} ·{' '}
                    {enrollment.academic_year_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FormField>

          <div className="grid gap-4 sm:grid-cols-2">
            <FormField
              id="issue_date"
              label={t('issueDate')}
              error={errors.issue_date?.message}
              required
            >
              <Input
                id="issue_date"
                type="date"
                aria-invalid={Boolean(errors.issue_date)}
                aria-describedby={describedBy('issue_date', errors.issue_date?.message)}
                {...form.register('issue_date')}
              />
            </FormField>

            <FormField
              id="due_date"
              label={t('dueDate')}
              hint={t('dueDateHint')}
              error={errors.due_date?.message}
            >
              <Input id="due_date" type="date" {...form.register('due_date')} />
            </FormField>
          </div>

          <fieldset className="space-y-3">
            <legend className="text-sm font-medium">{t('lines')}</legend>

            {lines.fields.map((field, index) => (
              <div key={field.id} className="grid gap-2 sm:grid-cols-[1fr_5rem_7rem_auto]">
                <FormField
                  id={`lines.${index}.description`}
                  label={t('lineDescription')}
                  error={errors.lines?.[index]?.description?.message}
                  required
                >
                  <Input
                    id={`lines.${index}.description`}
                    {...form.register(`lines.${index}.description` as const)}
                  />
                </FormField>

                <FormField
                  id={`lines.${index}.quantity`}
                  label={t('quantity')}
                  error={errors.lines?.[index]?.quantity?.message}
                >
                  <Input
                    id={`lines.${index}.quantity`}
                    inputMode="decimal"
                    {...form.register(`lines.${index}.quantity` as const)}
                  />
                </FormField>

                <FormField
                  id={`lines.${index}.unit_price`}
                  label={t('unitPrice')}
                  error={errors.lines?.[index]?.unit_price?.message}
                  required
                >
                  <Input
                    id={`lines.${index}.unit_price`}
                    inputMode="decimal"
                    {...form.register(`lines.${index}.unit_price` as const)}
                  />
                </FormField>

                <div className="flex items-end pb-1">
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    // An invoice needs at least one line; the API rejects an
                    // empty list, so the last row cannot be removed.
                    disabled={lines.fields.length === 1}
                    aria-label={t('removeLine')}
                    onClick={() => lines.remove(index)}
                  >
                    <Trash2 aria-hidden />
                  </Button>
                </div>
              </div>
            ))}

            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => lines.append({ ...EMPTY_LINE })}
            >
              <Plus aria-hidden />
              {t('addLine')}
            </Button>
          </fieldset>

          <FormField id="notes" label={t('notes')}>
            <Input id="notes" {...form.register('notes')} />
          </FormField>

          <div className="flex items-center justify-between rounded-md border border-border px-3 py-2">
            <span className="text-sm text-muted-foreground">{t('subtotal')}</span>
            <span className="font-medium tabular-nums">
              {formatCurrency(subtotal, currency, locale)}
            </span>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={form.formState.isSubmitting}
            >
              {tc('cancel')}
            </Button>
            <Button type="submit" disabled={form.formState.isSubmitting}>
              {form.formState.isSubmitting ? (
                <Loader2 className="animate-spin" aria-hidden />
              ) : null}
              {t('issueInvoice')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
