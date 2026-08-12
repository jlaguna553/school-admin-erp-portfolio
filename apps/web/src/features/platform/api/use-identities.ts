'use client';

import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type { ListParams } from '@/lib/crud';

import {
  createIdentity,
  deactivateIdentity,
  grantMembership,
  listIdentities,
  revokeMembership,
  setIdentityPassword,
  updateIdentity,
  type IdentityPayload,
} from './identity-api';

export const identityKeys = {
  all: ['platform', 'identities'] as const,
  list: (params: ListParams) => ['platform', 'identities', 'list', params] as const,
};

export function useIdentities(params: ListParams) {
  return useQuery({
    queryKey: identityKeys.list(params),
    queryFn: () => listIdentities(params),
    placeholderData: keepPreviousData,
  });
}

function useInvalidateIdentities() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: identityKeys.all });
}

export function useCreateIdentity() {
  const invalidate = useInvalidateIdentities();
  return useMutation({
    mutationFn: (payload: IdentityPayload) => createIdentity(payload),
    onSuccess: invalidate,
  });
}

export function useUpdateIdentity() {
  const invalidate = useInvalidateIdentities();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<IdentityPayload> }) =>
      updateIdentity(id, payload),
    onSuccess: invalidate,
  });
}

export function useDeactivateIdentity() {
  const invalidate = useInvalidateIdentities();
  return useMutation({
    mutationFn: (id: string) => deactivateIdentity(id),
    onSuccess: invalidate,
  });
}

export function useSetIdentityPassword() {
  return useMutation({
    mutationFn: ({ id, password }: { id: string; password: string }) =>
      setIdentityPassword(id, password),
  });
}

export function useGrantMembership() {
  const invalidate = useInvalidateIdentities();
  return useMutation({
    mutationFn: ({
      identityId,
      tenant,
      role,
    }: {
      identityId: string;
      tenant: string;
      role: string;
    }) => grantMembership(identityId, { tenant, role }),
    onSuccess: invalidate,
  });
}

export function useRevokeMembership() {
  const invalidate = useInvalidateIdentities();
  return useMutation({
    mutationFn: ({ identityId, membershipId }: { identityId: string; membershipId: string }) =>
      revokeMembership(identityId, membershipId),
    onSuccess: invalidate,
  });
}
