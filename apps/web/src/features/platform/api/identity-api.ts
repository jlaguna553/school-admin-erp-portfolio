import { apiClient } from '@/lib/api-client';
import { createOne, deactivateOne, fetchList, type ListParams } from '@/lib/crud';
import type { Membership, Paginated, PlatformIdentity } from '@erp/api-types';

/**
 * People who work at more than one school.
 *
 * Served on the platform host only. The membership list is the sensitive part:
 * it says which schools employ a given person, which no single school is
 * entitled to read about another.
 */
export const IDENTITIES_PATH = '/api/v1/identities/';

export interface IdentityPayload {
  email: string;
  first_name: string;
  last_name: string;
  phone?: string;
  language: string;
  password?: string;
}

export function listIdentities(params: ListParams): Promise<Paginated<PlatformIdentity>> {
  return fetchList<PlatformIdentity>(IDENTITIES_PATH, params);
}

export function createIdentity(payload: IdentityPayload): Promise<PlatformIdentity> {
  return createOne<PlatformIdentity>(IDENTITIES_PATH, payload);
}

export async function updateIdentity(
  id: string,
  payload: Partial<IdentityPayload>,
): Promise<PlatformIdentity> {
  const { data } = await apiClient.patch<PlatformIdentity>(`${IDENTITIES_PATH}${id}/`, payload);
  return data;
}

/** Soft delete: blocks sign-in at every school at once. */
export function deactivateIdentity(id: string): Promise<void> {
  return deactivateOne(IDENTITIES_PATH, id);
}

/**
 * Operator-initiated reset.
 *
 * There is one credential, so there is nothing to propagate afterwards — which
 * is exactly why this is the recovery path when someone is locked out
 * everywhere at once.
 */
export async function setIdentityPassword(id: string, newPassword: string): Promise<void> {
  await apiClient.post(`${IDENTITIES_PATH}${id}/set-password/`, { new_password: newPassword });
}

export async function grantMembership(
  identityId: string,
  payload: { tenant: string; role: string },
): Promise<Membership> {
  const { data } = await apiClient.post<Membership>(
    `${IDENTITIES_PATH}${identityId}/memberships/`,
    payload,
  );
  return data;
}

export async function revokeMembership(
  identityId: string,
  membershipId: string,
): Promise<void> {
  await apiClient.delete(`${IDENTITIES_PATH}${identityId}/memberships/${membershipId}/`);
}
