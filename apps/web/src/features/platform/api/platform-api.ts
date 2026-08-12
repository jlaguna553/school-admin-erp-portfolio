import { apiClient } from '@/lib/api-client';
import {
  createOne,
  deactivateOne,
  fetchList,
  fetchOne,
  updateOne,
  type ListParams,
} from '@/lib/crud';
import type { Institution, Paginated, User } from '@erp/api-types';

/**
 * The platform-operator API.
 *
 * These paths sit on the same origin as everything else now -- one domain
 * serves the whole platform -- so the `IsPlatformAdmin` permission is the whole
 * of the separation. It requires the caller to be platform staff acting on the
 * public schema, which a school administrator's token never is, however they
 * discover the URL.
 */
export const INSTITUTIONS_PATH = '/api/v1/tenants/';

export interface InstitutionFormPayload {
  name: string;
  legal_name?: string;
  tax_id?: string;
  default_language: string;
  default_currency: string;
  timezone?: string;
  brand_color?: string;
  /** Modules switched *off*. Empty means the institution runs everything. */
  disabled_modules?: string[];
}

export function listInstitutions(params: ListParams): Promise<Paginated<Institution>> {
  return fetchList<Institution>(INSTITUTIONS_PATH, params);
}

export function fetchInstitution(id: string): Promise<Institution> {
  return fetchOne<Institution>(INSTITUTIONS_PATH, id);
}

/**
 * Onboard a school.
 *
 * Slower than an ordinary create by a wide margin: the API creates a dedicated
 * Postgres schema and runs the whole tenant migration set inside it before
 * responding, so the UI must not treat a few seconds as a hang.
 */
export function createInstitution(payload: InstitutionFormPayload): Promise<Institution> {
  return createOne<Institution>(INSTITUTIONS_PATH, payload);
}

export function updateInstitution(
  id: string,
  payload: Partial<InstitutionFormPayload>,
): Promise<Institution> {
  return updateOne<Institution>(INSTITUTIONS_PATH, id, payload);
}

/** Soft delete: the school is deactivated but its schema and data survive. */
export function deactivateInstitution(id: string): Promise<void> {
  return deactivateOne(INSTITUTIONS_PATH, id);
}

// --- Users inside one institution ------------------------------------------
export function institutionUsersPath(institutionId: string): string {
  return `${INSTITUTIONS_PATH}${institutionId}/users/`;
}

export interface InstitutionUserPayload {
  email: string;
  first_name: string;
  last_name: string;
  phone?: string;
  role: string;
  language: string;
  password?: string;
}

export function listInstitutionUsers(
  institutionId: string,
  params: ListParams,
): Promise<Paginated<User>> {
  return fetchList<User>(institutionUsersPath(institutionId), params);
}

export function createInstitutionUser(
  institutionId: string,
  payload: InstitutionUserPayload,
): Promise<User> {
  return createOne<User>(institutionUsersPath(institutionId), payload);
}

export function updateInstitutionUser(
  institutionId: string,
  id: string,
  payload: Partial<InstitutionUserPayload>,
): Promise<User> {
  return updateOne<User>(institutionUsersPath(institutionId), id, payload);
}

export function deactivateInstitutionUser(
  institutionId: string,
  id: string,
): Promise<void> {
  return deactivateOne(institutionUsersPath(institutionId), id);
}

export interface RoleChoice {
  value: string;
  label: string;
}

/**
 * Roles assignable inside a school.
 *
 * Read from the platform host, so the list is the *public* schema's — which
 * includes `platform_admin`. The school-scoped endpoint refuses that role, so
 * it is filtered out by the caller rather than offered and then rejected.
 */
export async function listAssignableRoles(): Promise<RoleChoice[]> {
  const { data } = await apiClient.get<RoleChoice[]>('/api/v1/users/roles/');
  return data.filter((role) => role.value !== 'platform_admin');
}
