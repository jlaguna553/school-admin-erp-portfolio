import {
  createOne,
  deactivateOne,
  fetchList,
  updateOne,
  type ListParams,
} from '@/lib/crud';
import type { Paginated, User } from '@erp/api-types';

export const USERS_PATH = '/api/v1/users/';

export interface UserFormPayload {
  email: string;
  first_name: string;
  last_name: string;
  phone?: string;
  role: string;
  language: string;
  password?: string;
}

export function listUsers(params: ListParams): Promise<Paginated<User>> {
  return fetchList<User>(USERS_PATH, params);
}

export function createUser(payload: UserFormPayload): Promise<User> {
  return createOne<User>(USERS_PATH, payload);
}

export function updateUser(id: string, payload: Partial<UserFormPayload>): Promise<User> {
  return updateOne<User>(USERS_PATH, id, payload);
}

/** Soft delete: the row is kept and login is blocked. */
export function deactivateUser(id: string): Promise<void> {
  return deactivateOne(USERS_PATH, id);
}

export interface RoleChoice {
  value: string;
  label: string;
}

export async function listRoles(): Promise<RoleChoice[]> {
  const { apiClient } = await import('@/lib/api-client');
  const { data } = await apiClient.get<RoleChoice[]>(`${USERS_PATH}roles/`);
  return data;
}
