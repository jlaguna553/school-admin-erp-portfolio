'use client';

import type { ColumnDef } from '@tanstack/react-table';
import { Eye, Plus, Search } from 'lucide-react';
import { useLocale, useTranslations } from 'next-intl';
import { useMemo, useState } from 'react';

import { Button } from '@/components/ui/button';
import { DataTable } from '@/components/ui/data-table';
import { Input } from '@/components/ui/input';
import { PageHeader } from '@/components/layout/page-header';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useListControls } from '@/hooks/use-list-controls';
import { formatCurrency } from '@/lib/utils';
import type { Invoice } from '@erp/api-types';

import { useInvoices } from '../api/use-billing';
import { InvoiceDetailDialog } from './invoice-detail-dialog';
import { InvoiceFormDialog } from './invoice-form-dialog';
import { InvoiceStatusBadge } from './invoice-status-badge';

const ALL_STATUSES = '__all__';
const STATUSES = [
  'draft',
  'issued',
  'partially_paid',
  'paid',
  'overdue',
  'cancelled',
] as const;

export function BillingView() {
  const t = useTranslations('billing');
  const locale = useLocale();

  const [status, setStatus] = useState<string>(ALL_STATUSES);
  const filters = useMemo(
    () => (status === ALL_STATUSES ? {} : { status }),
    [status],
  );
  const controls = useListControls({
    initialSorting: [{ id: 'issue_date', desc: true }],
    filters,
  });

  const { data, isLoading, isFetching } = useInvoices(controls.params);
  const [selected, setSelected] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  const dateFormatter = useMemo(
    () => new Intl.DateTimeFormat(locale, { dateStyle: 'short', timeZone: 'UTC' }),
    [locale],
  );

  const columns = useMemo<ColumnDef<Invoice, unknown>[]>(
    () => [
      {
        id: 'number',
        accessorKey: 'number',
        header: t('number'),
        cell: ({ row }) => <span className="font-mono text-xs">{row.original.number}</span>,
      },
      {
        id: 'student',
        accessorKey: 'student_name_snapshot',
        header: t('student'),
        enableSorting: false,
        cell: ({ row }) => (
          <span className="font-medium">{row.original.student_name_snapshot}</span>
        ),
      },
      {
        id: 'issue_date',
        accessorKey: 'issue_date',
        header: t('issueDate'),
        cell: ({ row }) =>
          dateFormatter.format(new Date(`${row.original.issue_date}T00:00:00Z`)),
      },
      {
        id: 'due_date',
        accessorKey: 'due_date',
        header: t('dueDate'),
        cell: ({ row }) =>
          dateFormatter.format(new Date(`${row.original.due_date}T00:00:00Z`)),
      },
      {
        id: 'balance',
        accessorKey: 'balance',
        header: t('balance'),
        enableSorting: false,
        cell: ({ row }) => (
          <span className="tabular font-medium">
            {formatCurrency(row.original.balance, row.original.currency, locale)}
          </span>
        ),
      },
      {
        id: 'status',
        accessorKey: 'status',
        header: t('statusColumn'),
        enableSorting: false,
        cell: ({ row }) => <InvoiceStatusBadge status={row.original.status} />,
      },
      {
        id: 'actions',
        header: '',
        enableSorting: false,
        cell: ({ row }) => (
          <div className="flex justify-end">
            <Button
              variant="ghost"
              size="icon"
              aria-label={`${t('viewInvoice')}: ${row.original.number}`}
              onClick={() => setSelected(row.original.id)}
            >
              <Eye aria-hidden />
            </Button>
          </div>
        ),
      },
    ],
    [t, dateFormatter, locale],
  );

  return (
    <div className="space-y-5">
      <PageHeader
        title={t('title')}
        description={t('subtitle')}
        actions={
          <Button onClick={() => setCreating(true)}>
            <Plus aria-hidden />
            {t('newInvoice')}
          </Button>
        }
      />

      <div className="flex flex-wrap items-center gap-2">
        <div className="relative max-w-sm flex-1">
          <Search
            className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground"
            aria-hidden
          />
          <Input
            type="search"
            className="pl-8"
            placeholder={t('searchPlaceholder')}
            aria-label={t('searchPlaceholder')}
            value={controls.search}
            onChange={(event) => controls.setSearch(event.target.value)}
          />
        </div>

        <Select value={status} onValueChange={setStatus}>
          <SelectTrigger className="w-48" aria-label={t('filterByStatus')}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL_STATUSES}>{t('allStatuses')}</SelectItem>
            {STATUSES.map((value) => (
              <SelectItem key={value} value={value}>
                {t(`status.${value}`)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <DataTable
        columns={columns}
        data={data?.results ?? []}
        totalCount={data?.count ?? 0}
        totalPages={data?.total_pages ?? 1}
        page={controls.page}
        onPageChange={controls.setPage}
        sorting={controls.sorting}
        onSortingChange={controls.setSorting}
        isLoading={isLoading}
        isFetching={isFetching}
        emptyMessage={t('empty')}
      />

      <InvoiceFormDialog open={creating} onOpenChange={setCreating} />

      <InvoiceDetailDialog
        invoiceId={selected}
        onOpenChange={(open) => !open && setSelected(null)}
      />
    </div>
  );
}
