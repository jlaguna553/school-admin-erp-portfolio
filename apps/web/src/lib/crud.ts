import type { SortingState } from '@tanstack/react-table';

import { apiClient } from './api-client';
import type { Paginated } from '@erp/api-types';

/** Query params shared by every list endpoint. */
export interface ListParams {
  page?: number;
  page_size?: number;
  search?: string;
  ordering?: string;
  [filter: string]: string | number | boolean | undefined;
}

/**
 * Translate TanStack's sorting state into DRF's `ordering` parameter.
 *
 * DRF expects a comma-separated list with `-` for descending, which is why
 * sorting must round-trip to the server rather than being applied client-side:
 * ordering one page of 25 rows is not the same as ordering the dataset.
 */
export function toOrdering(sorting: SortingState): string | undefined {
  if (sorting.length === 0) return undefined;
  return sorting.map((rule) => (rule.desc ? `-${rule.id}` : rule.id)).join(',');
}

/** Drop empty values so they never reach the API as `?search=`. */
export function cleanParams(params: ListParams): ListParams {
  return Object.fromEntries(
    Object.entries(params).filter(
      ([, value]) => value !== undefined && value !== '' && value !== null,
    ),
  );
}

export async function fetchList<T>(path: string, params: ListParams): Promise<Paginated<T>> {
  const { data } = await apiClient.get<Paginated<T>>(path, { params: cleanParams(params) });
  return data;
}

export async function fetchOne<T>(path: string, id: string): Promise<T> {
  const { data } = await apiClient.get<T>(`${path}${id}/`);
  return data;
}

export async function createOne<T>(path: string, payload: unknown): Promise<T> {
  const { data } = await apiClient.post<T>(path, payload);
  return data;
}

export async function updateOne<T>(
  path: string,
  id: string,
  payload: unknown,
): Promise<T> {
  const { data } = await apiClient.patch<T>(`${path}${id}/`, payload);
  return data;
}

/**
 * Deactivate a record.
 *
 * The API implements `DELETE` as a soft delete, so nothing is destroyed — the
 * row is retained with `is_active=false`. UI copy should say "deactivate".
 */
export async function deactivateOne(path: string, id: string): Promise<void> {
  await apiClient.delete(`${path}${id}/`);
}
