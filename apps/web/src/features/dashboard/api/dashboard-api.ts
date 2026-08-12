import { apiClient } from '@/lib/api-client';
import type { Paginated } from '@erp/api-types';

/**
 * Dashboard figures.
 *
 * These are read from the real list endpoints using `page_size=1` and taking the
 * pagination `count`, which is why `DefaultPagination` returns `count` at all.
 * It is one cheap query per tile and needs no new backend surface.
 *
 * When the tile count grows, replace this with a single purpose-built
 * `GET /api/v1/dashboard/metrics/` aggregate — at that point one round trip beats
 * six, and the counts can be computed in one SQL pass.
 */
async function countOf(path: string, params: Record<string, string>): Promise<number> {
  const { data } = await apiClient.get<Paginated<unknown>>(path, {
    params: { ...params, page_size: 1 },
  });
  return data.count;
}

export interface DashboardMetrics {
  students: number;
  teachers: number;
  activeEnrollments: number;
  overdueInvoices: number;
}

export async function fetchDashboardMetrics(): Promise<DashboardMetrics> {
  const [students, teachers, activeEnrollments, overdueInvoices] = await Promise.all([
    countOf('/api/v1/users/', { role: 'student', is_active: 'true' }),
    countOf('/api/v1/users/', { role: 'teacher', is_active: 'true' }),
    countOf('/api/v1/academic/enrollments/', { status: 'active' }),
    // Billing is restricted to admins/accountants; a 403 must not blank the
    // whole dashboard, so this tile degrades to 0 for other roles.
    countOf('/api/v1/billing/invoices/', { status: 'overdue' }).catch(() => 0),
  ]);

  return { students, teachers, activeEnrollments, overdueInvoices };
}

export interface TrendPoint {
  /** ISO date (`YYYY-MM-DD`) — formatted for display in the active locale. */
  date: string;
  value: number;
}
