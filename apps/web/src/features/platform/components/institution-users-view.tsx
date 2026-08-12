'use client';

import type { ColumnDef } from '@tanstack/react-table';
import { ArrowLeft, Pencil, Plus, Search, UserX } from 'lucide-react';
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
import type { User } from '@erp/api-types';

import {
  useDeactivateInstitutionUser,
  useInstitution,
  useInstitutionUsers,
} from '../api/use-platform';
import { InstitutionUserFormDialog } from './institution-user-form-dialog';

interface InstitutionUsersViewProps {
  institutionId: string;
}

/**
 * The accounts inside one school, managed from the platform.
 *
 * The operator's way back into a school nobody can sign into any more: create a
 * fresh administrator, or restore a role that was changed by mistake.
 */
export function InstitutionUsersView({ institutionId }: InstitutionUsersViewProps) {
  const t = useTranslations('users');
  const tp = useTranslations('platform');
  const tc = useTranslations('common');

  const { data: institution } = useInstitution(institutionId);
  const controls = useListControls({ initialSorting: [{ id: 'last_name', desc: false }] });
  const { data, isLoading, isFetching } = useInstitutionUsers(institutionId, controls.params);
  const deactivate = useDeactivateInstitutionUser(institutionId);

  const [editing, setEditing] = useState<User | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [pendingDeactivation, setPendingDeactivation] = useState<User | null>(null);

  const columns = useMemo<ColumnDef<User, unknown>[]>(
    () => [
      {
        id: 'last_name',
        accessorFn: (row) => row.full_name,
        header: t('name'),
        // The row's only shrinkable column: its text truncates instead of
        // pushing the narrower columns out of view.
        meta: { cellClassName: 'w-full max-w-0' },
        cell: ({ row }) => (
          <div>
            <p className="truncate font-medium">{row.original.full_name}</p>
            <p className="truncate text-xs text-muted-foreground">{row.original.email}</p>
          </div>
        ),
      },
      {
        id: 'role',
        accessorKey: 'role',
        header: t('role'),
        enableSorting: false,
        cell: ({ row }) => <Badge variant="outline">{t(`roles.${row.original.role}`)}</Badge>,
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
              aria-label={`${tc('edit')}: ${row.original.full_name}`}
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
              aria-label={`${t('deactivate')}: ${row.original.full_name}`}
              onClick={() => setPendingDeactivation(row.original)}
            >
              <UserX aria-hidden />
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
      toast.success(t('deactivated', { name: pendingDeactivation.full_name }));
    } catch (error) {
      toast.error(toApiError(error)?.message ?? tc('genericError'));
    } finally {
      setPendingDeactivation(null);
    }
  }

  return (
    <div className="space-y-5">
      <Button variant="ghost" size="sm" asChild className="-ml-2">
        <Link href="/platform">
          <ArrowLeft aria-hidden />
          {tp('backToInstitutions')}
        </Link>
      </Button>

      <PageHeader
        title={institution?.name ?? tp('institutionUsersTitle')}
        description={tp('institutionUsersSubtitle')}
        actions={
          <Button
            onClick={() => {
              setEditing(null);
              setFormOpen(true);
            }}
          >
            <Plus aria-hidden />
            {t('newUser')}
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
          placeholder={t('searchPlaceholder')}
          aria-label={t('searchPlaceholder')}
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
        emptyMessage={t('empty')}
      />

      <InstitutionUserFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        institutionId={institutionId}
        user={editing}
      />

      <AlertDialog
        open={Boolean(pendingDeactivation)}
        onOpenChange={(open) => !open && setPendingDeactivation(null)}
      >
        <AlertDialogContent>
          <AlertDialogTitle>{t('deactivateTitle')}</AlertDialogTitle>
          <AlertDialogDescription>
            {t('deactivateBody', { name: pendingDeactivation?.full_name ?? '' })}
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
