'use client';

import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
  type RowData,
  type SortingState,
} from '@tanstack/react-table';
import { ArrowDown, ArrowUp, ChevronsUpDown, Inbox } from 'lucide-react';
import { useTranslations } from 'next-intl';

import { Button } from '@/components/ui/button';
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
import { cn } from '@/lib/utils';

/**
 * Per-column styling for the rendered `<td>`.
 *
 * The one that matters is `w-full max-w-0`, which makes a column the row's only
 * shrinkable one so its text truncates instead of pushing the narrower columns
 * out of view. It has to land on the cell: inside an auto-layout table a `<td>`
 * whose only content declares `max-width: 0` contributes no preferred width, so
 * the column collapses and `truncate` hides the content entirely.
 */
declare module '@tanstack/react-table' {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  interface ColumnMeta<TData extends RowData, TValue> {
    cellClassName?: string;
  }
}

export interface DataTableProps<TData> {
  columns: ColumnDef<TData, unknown>[];
  data: TData[];
  /** Total rows on the server, not the length of `data`. */
  totalCount: number;
  totalPages: number;
  page: number;
  onPageChange: (page: number) => void;
  sorting: SortingState;
  onSortingChange: (sorting: SortingState) => void;
  isLoading?: boolean;
  isFetching?: boolean;
  emptyMessage?: string;
}

/**
 * Table wired for **server-side** pagination and sorting.
 *
 * `manualPagination` / `manualSorting` tell TanStack Table not to slice or sort
 * locally: the API already returns exactly one page, and sorting the 25 rows in
 * hand would silently reorder only the current page rather than the dataset.
 */
export function DataTable<TData>({
  columns,
  data,
  totalCount,
  totalPages,
  page,
  onPageChange,
  sorting,
  onSortingChange,
  isLoading = false,
  isFetching = false,
  emptyMessage,
}: DataTableProps<TData>) {
  const t = useTranslations('table');

  const table = useReactTable({
    data,
    columns,
    state: { sorting },
    manualPagination: true,
    manualSorting: true,
    pageCount: totalPages,
    onSortingChange: (updater) => {
      onSortingChange(typeof updater === 'function' ? updater(sorting) : updater);
    },
    getCoreRowModel: getCoreRowModel(),
  });

  const columnCount = columns.length;

  return (
    <div className="space-y-3">
      <div
        className={cn(
          'rounded-lg border border-border bg-card transition-opacity',
          // Dim during a background refetch so the table does not appear frozen.
          isFetching && !isLoading && 'opacity-60',
        )}
      >
        <TableWrapper>
          <Table>
            <TableHeader>
              {table.getHeaderGroups().map((headerGroup) => (
                <TableRow key={headerGroup.id}>
                  {headerGroup.headers.map((header) => {
                    const canSort = header.column.getCanSort();
                    const sorted = header.column.getIsSorted();

                    return (
                      <TableHead
                        key={header.id}
                        scope="col"
                        aria-sort={
                          !sorted ? 'none' : sorted === 'asc' ? 'ascending' : 'descending'
                        }
                      >
                        {header.isPlaceholder ? null : canSort ? (
                          <button
                            type="button"
                            onClick={header.column.getToggleSortingHandler()}
                            className="inline-flex items-center gap-1 rounded transition-colors hover:text-foreground"
                          >
                            {flexRender(
                              header.column.columnDef.header,
                              header.getContext(),
                            )}
                            {sorted === 'asc' ? (
                              <ArrowUp className="size-3" aria-hidden />
                            ) : sorted === 'desc' ? (
                              <ArrowDown className="size-3" aria-hidden />
                            ) : (
                              <ChevronsUpDown className="size-3 opacity-40" aria-hidden />
                            )}
                          </button>
                        ) : (
                          flexRender(header.column.columnDef.header, header.getContext())
                        )}
                      </TableHead>
                    );
                  })}
                </TableRow>
              ))}
            </TableHeader>

            <TableBody>
              {isLoading ? (
                Array.from({ length: 5 }, (_, rowIndex) => (
                  <TableRow key={rowIndex}>
                    {Array.from({ length: columnCount }, (_, cellIndex) => (
                      <TableCell key={cellIndex}>
                        <Skeleton className="h-4 w-full" />
                      </TableCell>
                    ))}
                  </TableRow>
                ))
              ) : table.getRowModel().rows.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={columnCount} className="py-12">
                    <div className="flex flex-col items-center gap-2 text-center">
                      <Inbox className="size-6 text-muted-foreground" aria-hidden />
                      <p className="text-sm text-muted-foreground">
                        {emptyMessage ?? t('empty')}
                      </p>
                    </div>
                  </TableCell>
                </TableRow>
              ) : (
                table.getRowModel().rows.map((row) => (
                  <TableRow key={row.id}>
                    {row.getVisibleCells().map((cell) => (
                      <TableCell
                        key={cell.id}
                        className={cell.column.columnDef.meta?.cellClassName}
                      >
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </TableCell>
                    ))}
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableWrapper>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-muted-foreground" aria-live="polite">
          {t('summary', { count: totalCount, page, totalPages: Math.max(totalPages, 1) })}
        </p>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(page - 1)}
            disabled={page <= 1 || isLoading}
          >
            {t('previous')}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(page + 1)}
            disabled={page >= totalPages || isLoading}
          >
            {t('next')}
          </Button>
        </div>
      </div>
    </div>
  );
}
