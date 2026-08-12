'use client';

import type { ColumnDef } from '@tanstack/react-table';
import { Ban, Pencil, Plus, Search, Users } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { useMemo, useState } from 'react';
import { toast } from 'sonner';

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { DataTable } from '@/components/ui/data-table';
import { Input } from '@/components/ui/input';
import { PageHeader } from '@/components/layout/page-header';
import { useListControls } from '@/hooks/use-list-controls';
import { Link } from '@/i18n/navigation';
import { toApiError } from '@/lib/api-client';
import type { Institution } from '@erp/api-types';

import { useDeactivateInstitution, useInstitutions } from '../api/use-platform';
import { InstitutionFormDialog } from './institution-form-dialog';

/**
 * Every school on the platform.
 *
 * Reachable only on the platform host: the schools' own hostnames serve a
 * different URLconf where these routes do not exist.
 */
export function InstitutionsView() {
  const t = useTranslations('platform');
  const tc = useTranslations('common');

  const controls = useListControls({ initialSorting: [{ id: 'name', desc: false }] });
  const { data, isLoading, isFetching } = useInstitutions(controls.params);
  const deactivate = useDeactivateInstitution();

  const [editing, setEditing] = useState<Institution | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [pendingDeactivation, setPendingDeactivation] = useState<Institution | null>(null);

  const columns = useMemo<ColumnDef<Institution, unknown>[]>(
    () => [
      {
        id: 'name',
        accessorKey: 'name',
        header: t('name'),
        // The row's only shrinkable column: its text truncates instead of
        // pushing the narrower columns out of view.
        meta: { cellClassName: 'w-full max-w-0' },
        cell: ({ row }) => (
          <div>
            <p className="truncate font-medium">{row.original.name}</p>
            <p className="truncate text-xs text-muted-foreground">
              {row.original.schema_name}
            </p>
          </div>
        ),
      },
      {
        id: 'default_currency',
        accessorKey: 'default_currency',
        header: t('currency'),
        enableSorting: false,
        cell: ({ row }) => (
          <Badge variant="outline">{row.original.default_currency ?? 'MXN'}</Badge>
        ),
      },
      {
        id: 'is_active',
        accessorKey: 'is_active',
        header: t('status'),
        enableSorting: false,
        cell: ({ row }) => (
          <Badge variant={row.original.is_active ? 'success' : 'neutral'}>
            {row.original.is_active ? t('active') : t('inactive')}
          </Badge>
        ),
      },
      {
        id: 'actions',
        header: '',
        enableSorting: false,
        cell: ({ row }) => (
          <div className="flex justify-end gap-1">
            <Button
              variant="ghost"
              size="icon"
              asChild
              aria-label={`${t('manageUsers')}: ${row.original.name}`}
            >
              <Link href={`/platform/${row.original.id}/users`}>
                <Users aria-hidden />
              </Link>
            </Button>
            <Button
              variant="ghost"
              size="icon"
              aria-label={`${tc('edit')}: ${row.original.name}`}
              onClick={() => {
                setEditing(row.original);
                setFormOpen(true);
              }}
            >
              <Pencil aria-hidden />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              disabled={!row.original.is_active}
              aria-label={`${t('deactivate')}: ${row.original.name}`}
              onClick={() => setPendingDeactivation(row.original)}
            >
              <Ban aria-hidden />
            </Button>
          </div>
        ),
      },
    ],
    [t, tc],
  );

  async function confirmDeactivation() {
    if (!pendingDeactivation) return;
    try {
      await deactivate.mutateAsync(pendingDeactivation.id);
      toast.success(t('institutionDeactivated', { name: pendingDeactivation.name }));
    } catch (error) {
      toast.error(toApiError(error)?.message ?? tc('genericError'));
    } finally {
      setPendingDeactivation(null);
    }
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title={t('institutionsTitle')}
        description={t('institutionsSubtitle')}
        actions={
          <Button
            onClick={() => {
              setEditing(null);
              setFormOpen(true);
            }}
          >
            <Plus aria-hidden />
            {t('newInstitution')}
          </Button>
        }
      />

      <div className="relative max-w-sm">
        <Search
          className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground"
          aria-hidden
        />
        <Input
          type="search"
          className="pl-8"
          placeholder={t('searchInstitutions')}
          aria-label={t('searchInstitutions')}
          value={controls.search}
          onChange={(event) => controls.setSearch(event.target.value)}
        />
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
        emptyMessage={t('noInstitutions')}
      />

      <InstitutionFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        institution={editing}
      />

      <AlertDialog
        open={Boolean(pendingDeactivation)}
        onOpenChange={(open) => !open && setPendingDeactivation(null)}
      >
        <AlertDialogContent>
          <AlertDialogTitle>{t('deactivateInstitutionTitle')}</AlertDialogTitle>
          {/* The schema and every row in it survive -- only access stops. */}
          <AlertDialogDescription>
            {t('deactivateInstitutionBody', { name: pendingDeactivation?.name ?? '' })}
          </AlertDialogDescription>
          <AlertDialogFooter>
            <AlertDialogCancel>{tc('cancel')}</AlertDialogCancel>
            <AlertDialogAction variant="destructive" onClick={confirmDeactivation}>
              {t('deactivate')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
