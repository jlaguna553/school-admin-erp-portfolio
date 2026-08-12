'use client';

import type { ColumnDef } from '@tanstack/react-table';
import { Ban, Pencil, Plus, Search } from 'lucide-react';
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useListControls } from '@/hooks/use-list-controls';
import { toApiError } from '@/lib/api-client';
import type { Subject } from '@erp/api-types';

import { useDeactivateSubject, useProgramOptions, useSubjects } from '../api/use-academic';
import { SubjectFormDialog } from './subject-form-dialog';

const ALL_PROGRAMS = '__all__';

export function SubjectsView() {
  const t = useTranslations('subjects');
  const ta = useTranslations('academic');
  const tc = useTranslations('common');

  const [programFilter, setProgramFilter] = useState<string>(ALL_PROGRAMS);
  const { data: programs = [] } = useProgramOptions();

  const filters = useMemo(
    () => (programFilter === ALL_PROGRAMS ? {} : { program: programFilter }),
    [programFilter],
  );
  const controls = useListControls({
    initialSorting: [{ id: 'code', desc: false }],
    filters,
  });

  const { data, isLoading, isFetching } = useSubjects(controls.params);
  const deactivate = useDeactivateSubject();

  const [editing, setEditing] = useState<Subject | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [pending, setPending] = useState<Subject | null>(null);

  const columns = useMemo<ColumnDef<Subject, unknown>[]>(
    () => [
      {
        id: 'code',
        accessorKey: 'code',
        header: ta('code'),
        cell: ({ row }) => <span className="font-mono text-xs">{row.original.code}</span>,
      },
      {
        id: 'name',
        accessorKey: 'name',
        header: ta('name'),
        enableSorting: false,
        cell: ({ row }) => <span className="font-medium">{row.original.name}</span>,
      },
      {
        id: 'program',
        accessorKey: 'program_code',
        header: t('program'),
        enableSorting: false,
        cell: ({ row }) => <Badge variant="outline">{row.original.program_code}</Badge>,
      },
      {
        id: 'credits',
        accessorKey: 'credits',
        header: t('credits'),
        cell: ({ row }) => <span className="tabular">{row.original.credits}</span>,
      },
      {
        id: 'teacher',
        accessorKey: 'teacher_name',
        header: t('teacher'),
        enableSorting: false,
        cell: ({ row }) =>
          row.original.teacher_name ?? (
            <span className="text-muted-foreground">{t('unassigned')}</span>
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
              aria-label={`${ta('deactivate')}: ${row.original.name}`}
              onClick={() => setPending(row.original)}
            >
              <Ban aria-hidden />
            </Button>
          </div>
        ),
      },
    ],
    [t, ta, tc],
  );

  async function confirmDeactivation() {
    if (!pending) return;
    try {
      await deactivate.mutateAsync(pending.id);
      toast.success(t('deactivated'));
    } catch (error) {
      toast.error(toApiError(error)?.message ?? tc('genericError'));
    } finally {
      setPending(null);
    }
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title={t('title')}
        description={t('subtitle')}
        actions={
          <Button
            onClick={() => {
              setEditing(null);
              setFormOpen(true);
            }}
          >
            <Plus aria-hidden />
            {t('newSubject')}
          </Button>
        }
      />

      {/* Filters sit in one row above the table. */}
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

        <Select value={programFilter} onValueChange={setProgramFilter}>
          <SelectTrigger className="w-56" aria-label={t('filterByProgram')}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL_PROGRAMS}>{t('allPrograms')}</SelectItem>
            {programs.map((program) => (
              <SelectItem key={program.id} value={program.id}>
                {program.code} — {program.name}
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

      <SubjectFormDialog open={formOpen} onOpenChange={setFormOpen} subject={editing} />

      <AlertDialog open={Boolean(pending)} onOpenChange={(open) => !open && setPending(null)}>
        <AlertDialogContent>
          <AlertDialogTitle>{t('deactivateTitle')}</AlertDialogTitle>
          <AlertDialogDescription>{ta('deactivateBody')}</AlertDialogDescription>
          <AlertDialogFooter>
            <AlertDialogCancel>{tc('cancel')}</AlertDialogCancel>
            <AlertDialogAction variant="destructive" onClick={confirmDeactivation}>
              {ta('deactivate')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
