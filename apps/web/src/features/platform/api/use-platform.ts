'use client';

import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type { ListParams } from '@/lib/crud';

import {
  createInstitution,
  createInstitutionUser,
  deactivateInstitution,
  deactivateInstitutionUser,
  fetchInstitution,
  listAssignableRoles,
  listInstitutionUsers,
  listInstitutions,
  updateInstitution,
  updateInstitutionUser,
  type InstitutionFormPayload,
  type InstitutionUserPayload,
} from './platform-api';

export const platformKeys = {
  all: ['platform'] as const,
  institutions: ['platform', 'institutions'] as const,
  institutionList: (params: ListParams) => ['platform', 'institutions', 'list', params] as const,
  institution: (id: string) => ['platform', 'institutions', id] as const,
  users: (institutionId: string) => ['platform', 'institutions', institutionId, 'users'] as const,
  userList: (institutionId: string, params: ListParams) =>
    ['platform', 'institutions', institutionId, 'users', 'list', params] as const,
  roles: ['platform', 'roles'] as const,
};

export function useInstitutions(params: ListParams) {
  return useQuery({
    queryKey: platformKeys.institutionList(params),
    queryFn: () => listInstitutions(params),
    placeholderData: keepPreviousData,
  });
}

export function useInstitution(id: string) {
  return useQuery({
    queryKey: platformKeys.institution(id),
    queryFn: () => fetchInstitution(id),
    enabled: Boolean(id),
  });
}

export function useAssignableRoles() {
  return useQuery({
    queryKey: platformKeys.roles,
    queryFn: listAssignableRoles,
    staleTime: 10 * 60_000,
  });
}

function useInvalidateInstitutions() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: platformKeys.institutions });
}

export function useCreateInstitution() {
  const invalidate = useInvalidateInstitutions();
  return useMutation({
    mutationFn: (payload: InstitutionFormPayload) => createInstitution(payload),
    onSuccess: invalidate,
  });
}

export function useUpdateInstitution() {
  const invalidate = useInvalidateInstitutions();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<InstitutionFormPayload> }) =>
      updateInstitution(id, payload),
    onSuccess: invalidate,
  });
}

export function useDeactivateInstitution() {
  const invalidate = useInvalidateInstitutions();
  return useMutation({
    mutationFn: (id: string) => deactivateInstitution(id),
    onSuccess: invalidate,
  });
}

export function useInstitutionUsers(institutionId: string, params: ListParams) {
  return useQuery({
    queryKey: platformKeys.userList(institutionId, params),
    queryFn: () => listInstitutionUsers(institutionId, params),
    enabled: Boolean(institutionId),
    placeholderData: keepPreviousData,
  });
}

function useInvalidateInstitutionUsers(institutionId: string) {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: platformKeys.users(institutionId) });
}

export function useCreateInstitutionUser(institutionId: string) {
  const invalidate = useInvalidateInstitutionUsers(institutionId);
  return useMutation({
    mutationFn: (payload: InstitutionUserPayload) =>
      createInstitutionUser(institutionId, payload),
    onSuccess: invalidate,
  });
}

export function useUpdateInstitutionUser(institutionId: string) {
  const invalidate = useInvalidateInstitutionUsers(institutionId);
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<InstitutionUserPayload> }) =>
      updateInstitutionUser(institutionId, id, payload),
    onSuccess: invalidate,
  });
}

export function useDeactivateInstitutionUser(institutionId: string) {
  const invalidate = useInvalidateInstitutionUsers(institutionId);
  return useMutation({
    mutationFn: (id: string) => deactivateInstitutionUser(institutionId, id),
    onSuccess: invalidate,
  });
}
