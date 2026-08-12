'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { keepPreviousData } from '@tanstack/react-query';

import type { ListParams } from '@/lib/crud';

import {
  createUser,
  deactivateUser,
  listRoles,
  listUsers,
  updateUser,
  type UserFormPayload,
} from './users-api';

export const userKeys = {
  all: ['users'] as const,
  list: (params: ListParams) => ['users', 'list', params] as const,
  roles: ['users', 'roles'] as const,
};

export function useUsers(params: ListParams) {
  return useQuery({
    queryKey: userKeys.list(params),
    queryFn: () => listUsers(params),
    // Keeps the previous page on screen while the next one loads, so the table
    // does not collapse to a skeleton on every pagination click.
    placeholderData: keepPreviousData,
  });
}

export function useRoles() {
  return useQuery({
    queryKey: userKeys.roles,
    queryFn: listRoles,
    // Role labels are localized server-side but change only on deploy.
    staleTime: 10 * 60_000,
  });
}

function useInvalidateUsers() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: userKeys.all });
}

export function useCreateUser() {
  const invalidate = useInvalidateUsers();
  return useMutation({
    mutationFn: (payload: UserFormPayload) => createUser(payload),
    onSuccess: invalidate,
  });
}

export function useUpdateUser() {
  const invalidate = useInvalidateUsers();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<UserFormPayload> }) =>
      updateUser(id, payload),
    onSuccess: invalidate,
  });
}

export function useDeactivateUser() {
  const invalidate = useInvalidateUsers();
  return useMutation({
    mutationFn: (id: string) => deactivateUser(id),
    onSuccess: invalidate,
  });
}
