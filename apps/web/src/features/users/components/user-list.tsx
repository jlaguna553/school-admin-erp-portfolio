'use client';

import type { ColumnDef } from '@tanstack/react-table';
import { Pencil, Plus, Search, UserX } from 'lucide-react';
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
import { toApiError } from '@/lib/api-client';
import type { User } from '@erp/api-types';

import { useDeactivateUser, useUsers } from '../api/use-users';
import { UserFormDialog } from './user-form-dialog';

interface UserListProps {
  /** Restricts the list (and new records) to one role. */
  role?: string;
  title: string;
  description?: string;
}

export function UserList({ role, title, description }: UserListProps) {
  const t = useTranslations('users');
  const tc = useTranslations('common');

  const filters = useMemo(() => (role ? { role } : {}), [role]);
  const controls = useListControls({
    initialSorting: [{ id: 'last_name', desc: false }],
    filters,
  });

  const { data, isLoading, isFetching } = useUsers(controls.params);
  const deactivate = useDeactivateUser();

  const [editing, setEditing] = useState<User | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [pendingDeactivation, setPendingDeactivation] = useState<User | null>(null);

  const columns = useMemo<ColumnDef<User, unknown>[]>(
    () => [
      {
        id: 'last_name',
        accessorFn: (row) => row.full_name,
        header: t('name'),
        cell: ({ row }) => (
          <span className="font-medium">{row.original.full_name}</span>
        ),
      },
      {
        id: 'email',
        accessorKey: 'email',
        header: t('email'),
        cell: ({ row }) => (
          <span className="text-muted-foreground">{row.original.email}</span>
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
        id: 'phone',
        accessorKey: 'phone',
        header: t('phone'),
        enableSorting: false,
        cell: ({ row }) => row.original.phone || <span aria-hidden>—</span>,
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
      <PageHeader
        title={title}
        description={description}
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

      <UserFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        user={editing}
        defaultRole={role ?? 'student'}
        lockRole={Boolean(role)}
      />

      <AlertDialog
        open={Boolean(pendingDeactivation)}
        onOpenChange={(open) => !open && setPendingDeactivation(null)}
      >
        <AlertDialogContent>
          <AlertDialogTitle>{t('deactivateTitle')}</AlertDialogTitle>
          {/* Wording matters: this is a soft delete, so nothing is destroyed. */}
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
