'use client';

import type { SortingState } from '@tanstack/react-table';
import { useEffect, useMemo, useState } from 'react';

import { toOrdering, type ListParams } from '@/lib/crud';

interface UseListControlsOptions {
  initialSorting?: SortingState;
  pageSize?: number;
  /** Extra server-side filters, e.g. `{ role: 'student' }`. */
  filters?: Record<string, string | undefined>;
  debounceMs?: number;
}

/**
 * Pagination + sorting + debounced search for a server-driven list.
 *
 * Search is debounced so typing does not fire a request per keystroke, and any
 * change to the search text or filters resets to page 1 — otherwise a narrower
 * result set would leave the user stranded on a page that no longer exists.
 */
export function useListControls({
  initialSorting = [],
  pageSize = 25,
  filters = {},
  debounceMs = 300,
}: UseListControlsOptions = {}) {
  const [page, setPage] = useState(1);
  const [sorting, setSorting] = useState<SortingState>(initialSorting);
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), debounceMs);
    return () => clearTimeout(timer);
  }, [search, debounceMs]);

  const filterKey = JSON.stringify(filters);

  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, filterKey]);

  const params = useMemo<ListParams>(
    () => ({
      page,
      page_size: pageSize,
      search: debouncedSearch || undefined,
      ordering: toOrdering(sorting),
      ...filters,
    }),
    // `filterKey` stands in for `filters` so a fresh object literal each render
    // does not invalidate the memo (and therefore the query key) every time.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [page, pageSize, debouncedSearch, sorting, filterKey],
  );

  function handleSortingChange(next: SortingState) {
    setSorting(next);
    setPage(1);
  }

  return {
    page,
    setPage,
    sorting,
    setSorting: handleSortingChange,
    search,
    setSearch,
    params,
  };
}
