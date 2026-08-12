'use client';

import type { ColumnDef } from '@tanstack/react-table';
import { Ban, Pencil, Plus } from 'lucide-react';
import { useLocale, useTranslations } from 'next-intl';
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
import { PageHeader } from '@/components/layout/page-header';
import { useListControls } from '@/hooks/use-list-controls';
import { toApiError } from '@/lib/api-client';
import { cn } from '@/lib/utils';
import type { AcademicYear, Enrollment, Program } from '@erp/api-types';

import {
  useAcademicYears,
  useDeactivateAcademicYear,
  useDeactivateEnrollment,
  useDeactivateProgram,
  useEnrollments,
  usePrograms,
} from '../api/use-academic';
import { AcademicYearFormDialog } from './academic-year-form-dialog';
import { EnrollmentFormDialog } from './enrollment-form-dialog';
import { ProgramFormDialog } from './program-form-dialog';

type Tab = 'years' | 'programs' | 'enrollments';

export function AcademicView() {
  const t = useTranslations('academic');
  const [tab, setTab] = useState<Tab>('years');

  return (
    <div className="space-y-5">
      <PageHeader title={t('title')} description={t('subtitle')} />

      {/* Two related resources, one screen. A tablist keeps the sidebar flat
          instead of adding a nav entry per table. */}
      <div role="tablist" aria-label={t('title')} className="flex gap-1 border-b border-border">
        {(['years', 'programs', 'enrollments'] as const).map((value) => (
          <button
            key={value}
            role="tab"
            id={`tab-${value}`}
            aria-selected={tab === value}
            aria-controls={`panel-${value}`}
            onClick={() => setTab(value)}
            className={cn(
              '-mb-px border-b-2 px-3 py-2 text-sm transition-colors',
              tab === value
                ? 'border-primary font-medium text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground',
            )}
          >
            {t(`${value}Tab`)}
          </button>
        ))}
      </div>

      <div
        role="tabpanel"
        id={`panel-${tab}`}
        aria-labelledby={`tab-${tab}`}
      >
        {tab === 'years' ? <AcademicYearsTable /> : null}
        {tab === 'programs' ? <ProgramsTable /> : null}
        {tab === 'enrollments' ? <EnrollmentsTable /> : null}
      </div>
    </div>
  );
}

function AcademicYearsTable() {
  const t = useTranslations('academic');
  const tc = useTranslations('common');
  const locale = useLocale();

  const controls = useListControls({ initialSorting: [{ id: 'start_date', desc: true }] });
  const { data, isLoading, isFetching } = useAcademicYears(controls.params);
  const deactivate = useDeactivateAcademicYear();

  const [editing, setEditing] = useState<AcademicYear | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [pending, setPending] = useState<AcademicYear | null>(null);

  const dateFormatter = useMemo(
    () => new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeZone: 'UTC' }),
    [locale],
  );

  const columns = useMemo<ColumnDef<AcademicYear, unknown>[]>(
    () => [
      {
        id: 'name',
        accessorKey: 'name',
        header: t('yearName'),
        cell: ({ row }) => (
          <span className="flex items-center gap-2">
            <span className="font-medium">{row.original.name}</span>
            {row.original.is_current ? (
              <Badge variant="success">{t('current')}</Badge>
            ) : null}
          </span>
        ),
      },
      {
        id: 'start_date',
        accessorKey: 'start_date',
        header: t('startDate'),
        cell: ({ row }) =>
          dateFormatter.format(new Date(`${row.original.start_date}T00:00:00Z`)),
      },
      {
        id: 'end_date',
        accessorKey: 'end_date',
        header: t('endDate'),
        enableSorting: false,
        cell: ({ row }) =>
          dateFormatter.format(new Date(`${row.original.end_date}T00:00:00Z`)),
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
              aria-label={`${t('deactivate')}: ${row.original.name}`}
              onClick={() => setPending(row.original)}
            >
              <Ban aria-hidden />
            </Button>
          </div>
        ),
      },
    ],
    [t, tc, dateFormatter],
  );

  async function confirmDeactivation() {
    if (!pending) return;
    try {
      await deactivate.mutateAsync(pending.id);
      toast.success(t('yearDeactivated'));
    } catch (error) {
      toast.error(toApiError(error)?.message ?? tc('genericError'));
    } finally {
      setPending(null);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button
          onClick={() => {
            setEditing(null);
            setFormOpen(true);
          }}
        >
          <Plus aria-hidden />
          {t('newYear')}
        </Button>
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
        emptyMessage={t('noYears')}
      />

      <AcademicYearFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        academicYear={editing}
      />

      <AlertDialog open={Boolean(pending)} onOpenChange={(open) => !open && setPending(null)}>
        <AlertDialogContent>
          <AlertDialogTitle>{t('deactivateYearTitle')}</AlertDialogTitle>
          <AlertDialogDescription>{t('deactivateBody')}</AlertDialogDescription>
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

function ProgramsTable() {
  const t = useTranslations('academic');
  const tc = useTranslations('common');

  const controls = useListControls({ initialSorting: [{ id: 'code', desc: false }] });
  const { data, isLoading, isFetching } = usePrograms(controls.params);
  const deactivate = useDeactivateProgram();

  const [editingId, setEditingId] = useState<string | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [pending, setPending] = useState<Program | null>(null);

  const columns = useMemo<ColumnDef<Program, unknown>[]>(
    () => [
      {
        id: 'code',
        accessorKey: 'code',
        header: t('code'),
        cell: ({ row }) => <span className="font-mono text-xs">{row.original.code}</span>,
      },
      {
        id: 'name',
        accessorKey: 'name',
        header: t('name'),
        // Resolved for the active locale by modeltranslation.
        cell: ({ row }) => <span className="font-medium">{row.original.name}</span>,
      },
      {
        id: 'description',
        accessorKey: 'description',
        header: t('description'),
        enableSorting: false,
        cell: ({ row }) => (
          <span className="line-clamp-1 text-muted-foreground">
            {row.original.description || '—'}
          </span>
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
                setEditingId(row.original.id);
                setFormOpen(true);
              }}
            >
              <Pencil aria-hidden />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              aria-label={`${t('deactivate')}: ${row.original.name}`}
              onClick={() => setPending(row.original)}
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
    if (!pending) return;
    try {
      await deactivate.mutateAsync(pending.id);
      toast.success(t('programDeactivated'));
    } catch (error) {
      // Programmes are referenced by subjects with on_delete=PROTECT, so this
      // legitimately fails when one is in use — show the server's reason.
      toast.error(toApiError(error)?.message ?? tc('genericError'));
    } finally {
      setPending(null);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button
          onClick={() => {
            setEditingId(null);
            setFormOpen(true);
          }}
        >
          <Plus aria-hidden />
          {t('newProgram')}
        </Button>
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
        emptyMessage={t('noPrograms')}
      />

      <ProgramFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        programId={editingId}
      />

      <AlertDialog open={Boolean(pending)} onOpenChange={(open) => !open && setPending(null)}>
        <AlertDialogContent>
          <AlertDialogTitle>{t('deactivateProgramTitle')}</AlertDialogTitle>
          <AlertDialogDescription>{t('deactivateBody')}</AlertDialogDescription>
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

/**
 * Who is enrolled in what, and for which year.
 *
 * The record billing depends on: an invoice references an enrollment by bare
 * UUID (rule A.2 forbids the ForeignKey), and the billing service refuses any
 * enrollment that does not exist or is withdrawn. So this table is the gate
 * between the academic and financial sides of the ERP.
 */
function EnrollmentsTable() {
  const t = useTranslations('academic');
  const tc = useTranslations('common');
  const locale = useLocale();

  const controls = useListControls({ initialSorting: [{ id: 'enrolled_on', desc: true }] });
  const { data, isLoading, isFetching } = useEnrollments(controls.params);
  const deactivate = useDeactivateEnrollment();

  const [editing, setEditing] = useState<Enrollment | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [pending, setPending] = useState<Enrollment | null>(null);

  const dateFormatter = useMemo(
    () => new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeZone: 'UTC' }),
    [locale],
  );

  const columns = useMemo<ColumnDef<Enrollment, unknown>[]>(
    () => [
      {
        id: 'student',
        accessorFn: (row) => row.student_name,
        header: t('student'),
        enableSorting: false,
        // The row's only shrinkable column: its text truncates instead of
        // pushing the narrower columns out of view.
        meta: { cellClassName: 'w-full max-w-0' },
        cell: ({ row }) => (
          <div>
            <p className="truncate font-medium">{row.original.student_name}</p>
            <p className="truncate text-xs text-muted-foreground">
              {row.original.program_name}
            </p>
          </div>
        ),
      },
      {
        id: 'academic_year',
        accessorFn: (row) => row.academic_year_name,
        header: t('academicYear'),
        enableSorting: false,
        cell: ({ row }) => row.original.academic_year_name,
      },
      {
        id: 'status',
        accessorKey: 'status',
        header: t('status'),
        cell: ({ row }) => (
          <Badge
            variant={
              row.original.status === 'active'
                ? 'success'
                : row.original.status === 'withdrawn'
                  ? 'destructive'
                  : 'neutral'
            }
          >
            {t(`enrollmentStatuses.${row.original.status}`)}
          </Badge>
        ),
      },
      {
        id: 'enrolled_on',
        accessorKey: 'enrolled_on',
        header: t('enrolledOn'),
        cell: ({ row }) =>
          dateFormatter.format(new Date(`${row.original.enrolled_on}T00:00:00Z`)),
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
              aria-label={`${tc('edit')}: ${row.original.student_name}`}
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
              aria-label={`${t('deactivate')}: ${row.original.student_name}`}
              onClick={() => setPending(row.original)}
            >
              <Ban aria-hidden />
            </Button>
          </div>
        ),
      },
    ],
    [t, tc, dateFormatter],
  );

  async function confirmDeactivation() {
    if (!pending) return;
    try {
      await deactivate.mutateAsync(pending.id);
      toast.success(t('enrollmentDeactivated'));
    } catch (error) {
      toast.error(toApiError(error)?.message ?? tc('genericError'));
    } finally {
      setPending(null);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button
          onClick={() => {
            setEditing(null);
            setFormOpen(true);
          }}
        >
          <Plus aria-hidden />
          {t('newEnrollment')}
        </Button>
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
        emptyMessage={t('noEnrollments')}
      />

      <EnrollmentFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        enrollment={editing}
      />

      <AlertDialog open={Boolean(pending)} onOpenChange={(open) => !open && setPending(null)}>
        <AlertDialogContent>
          <AlertDialogTitle>{t('deactivateEnrollmentTitle')}</AlertDialogTitle>
          <AlertDialogDescription>{t('deactivateBody')}</AlertDialogDescription>
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
