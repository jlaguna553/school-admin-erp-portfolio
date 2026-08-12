'use client';

import type { ColumnDef } from '@tanstack/react-table';
import { Building2, Pencil, Plus, Search, UserX } from 'lucide-react';
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
import type { PlatformIdentity } from '@erp/api-types';

import { useDeactivateIdentity, useIdentities } from '../api/use-identities';
import { IdentityFormDialog } from './identity-form-dialog';
import { IdentitySchoolsDialog } from './identity-schools-dialog';

/**
 * People with a platform-wide credential.
 *
 * Distinct from a school's own users screen, which manages accounts that exist
 * at that school only. Someone appears here when they need one password across
 * more than one school — a head teacher covering two campuses, an accountant
 * shared between institutions.
 */
export function PeopleView() {
  const t = useTranslations('platform');
  const tu = useTranslations('users');
  const tc = useTranslations('common');

  const controls = useListControls({ initialSorting: [{ id: 'last_name', desc: false }] });
  const { data, isLoading, isFetching } = useIdentities(controls.params);
  const deactivate = useDeactivateIdentity();

  const [editing, setEditing] = useState<PlatformIdentity | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [managingSchools, setManagingSchools] = useState<PlatformIdentity | null>(null);
  const [pendingDeactivation, setPendingDeactivation] = useState<PlatformIdentity | null>(null);

  // The dialog has to follow the refetched row, or a granted school would not
  // appear until it is closed and reopened.
  const schoolsTarget = managingSchools
    ? (data?.results.find((row) => row.id === managingSchools.id) ?? managingSchools)
    : null;

  const columns = useMemo<ColumnDef<PlatformIdentity, unknown>[]>(
    () => [
      {
        id: 'last_name',
        accessorFn: (row) => row.full_name,
        header: tu('name'),
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
        id: 'schools',
        header: t('schools'),
        enableSorting: false,
        cell: ({ row }) => {
          const active = row.original.memberships.filter((m) => m.is_active);
          if (active.length === 0) {
            return <span className="text-xs text-muted-foreground">{t('noSchoolsYet')}</span>;
          }
          return (
            <div className="flex flex-wrap gap-1">
              {active.map((membership) => (
                <Badge key={membership.id} variant="outline">
                  {membership.tenant_name}
                </Badge>
              ))}
            </div>
          );
        },
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
              aria-label={`${t('manageSchools')}: ${row.original.full_name}`}
              onClick={() => setManagingSchools(row.original)}
            >
              <Building2 aria-hidden />
            </Button>
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
              aria-label={`${t('deactivatePerson')}: ${row.original.full_name}`}
              onClick={() => setPendingDeactivation(row.original)}
            >
              <UserX aria-hidden />
            </Button>
          </div>
        ),
      },
    ],
    [t, tu, tc],
  );

  async function confirmDeactivation() {
    if (!pendingDeactivation) return;
    try {
      await deactivate.mutateAsync(pendingDeactivation.id);
      toast.success(t('personDeactivated', { name: pendingDeactivation.full_name }));
    } catch (error) {
      toast.error(toApiError(error)?.message ?? tc('genericError'));
    } finally {
      setPendingDeactivation(null);
    }
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title={t('peopleTitle')}
        description={t('peopleSubtitle')}
        actions={
          <Button
            onClick={() => {
              setEditing(null);
              setFormOpen(true);
            }}
          >
            <Plus aria-hidden />
            {t('newPerson')}
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
          placeholder={t('searchPeople')}
          aria-label={t('searchPeople')}
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
        emptyMessage={t('noPeople')}
      />

      <IdentityFormDialog open={formOpen} onOpenChange={setFormOpen} identity={editing} />

      <IdentitySchoolsDialog
        open={Boolean(managingSchools)}
        onOpenChange={(open) => !open && setManagingSchools(null)}
        identity={schoolsTarget}
      />

      <AlertDialog
        open={Boolean(pendingDeactivation)}
        onOpenChange={(open) => !open && setPendingDeactivation(null)}
      >
        <AlertDialogContent>
          <AlertDialogTitle>{t('deactivatePersonTitle')}</AlertDialogTitle>
          {/* One credential means one place to revoke it — say so plainly. */}
          <AlertDialogDescription>
            {t('deactivatePersonBody', { name: pendingDeactivation?.full_name ?? '' })}
          </AlertDialogDescription>
          <AlertDialogFooter>
            <AlertDialogCancel>{tc('cancel')}</AlertDialogCancel>
            <AlertDialogAction variant="destructive" onClick={confirmDeactivation}>
              {t('deactivatePerson')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
