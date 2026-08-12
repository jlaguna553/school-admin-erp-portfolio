'use client';

import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type { ListParams } from '@/lib/crud';

import {
  createGroup,
  createSlot,
  deactivateGroup,
  deactivateSlot,
  fetchAttendanceTrend,
  fetchDayClasses,
  fetchRoll,
  fetchWeek,
  listAllGroups,
  listGroups,
  takeRoll,
  updateGroup,
  updateSlot,
  type GroupPayload,
  type RollEntry,
  type SlotPayload,
} from './schedule-api';

export const scheduleKeys = {
  all: ['schedule'] as const,
  groups: (params: ListParams) => ['schedule', 'groups', params] as const,
  groupOptions: ['schedule', 'group-options'] as const,
  week: (filters: Record<string, string | undefined>) => ['schedule', 'week', filters] as const,
  day: (filters: Record<string, string | undefined>) => ['schedule', 'day', filters] as const,
  roll: (slot: string, date: string) => ['schedule', 'roll', slot, date] as const,
  trend: (days: number) => ['schedule', 'trend', days] as const,
};

function useInvalidateSchedule() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: scheduleKeys.all });
}

// --- Groups -----------------------------------------------------------------
export function useGroups(params: ListParams) {
  return useQuery({
    queryKey: scheduleKeys.groups(params),
    queryFn: () => listGroups(params),
    placeholderData: keepPreviousData,
  });
}

export function useGroupOptions() {
  return useQuery({
    queryKey: scheduleKeys.groupOptions,
    queryFn: listAllGroups,
    staleTime: 60_000,
  });
}

export function useCreateGroup() {
  const invalidate = useInvalidateSchedule();
  return useMutation({ mutationFn: (p: GroupPayload) => createGroup(p), onSuccess: invalidate });
}

export function useUpdateGroup() {
  const invalidate = useInvalidateSchedule();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<GroupPayload> }) =>
      updateGroup(id, payload),
    onSuccess: invalidate,
  });
}

export function useDeactivateGroup() {
  const invalidate = useInvalidateSchedule();
  return useMutation({ mutationFn: (id: string) => deactivateGroup(id), onSuccess: invalidate });
}

// --- Timetable --------------------------------------------------------------
export function useWeek(filters: { group?: string; teacher?: string }) {
  return useQuery({
    queryKey: scheduleKeys.week(filters),
    queryFn: () => fetchWeek(filters),
    enabled: Boolean(filters.group || filters.teacher),
    placeholderData: keepPreviousData,
  });
}

export function useCreateSlot() {
  const invalidate = useInvalidateSchedule();
  return useMutation({ mutationFn: (p: SlotPayload) => createSlot(p), onSuccess: invalidate });
}

export function useUpdateSlot() {
  const invalidate = useInvalidateSchedule();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<SlotPayload> }) =>
      updateSlot(id, payload),
    onSuccess: invalidate,
  });
}

export function useDeactivateSlot() {
  const invalidate = useInvalidateSchedule();
  return useMutation({ mutationFn: (id: string) => deactivateSlot(id), onSuccess: invalidate });
}

// --- Attendance -------------------------------------------------------------
export function useDayClasses(filters: { date: string; teacher?: string; group?: string }) {
  return useQuery({
    queryKey: scheduleKeys.day(filters),
    queryFn: () => fetchDayClasses(filters),
    placeholderData: keepPreviousData,
  });
}

export function useRoll(slot: string | null, date: string) {
  return useQuery({
    queryKey: scheduleKeys.roll(slot ?? 'none', date),
    queryFn: () => fetchRoll(slot as string, date),
    enabled: Boolean(slot),
  });
}

export function useTakeRoll() {
  const invalidate = useInvalidateSchedule();
  return useMutation({
    mutationFn: (payload: {
      slot: string;
      date: string;
      status?: 'held' | 'cancelled';
      note?: string;
      entries: RollEntry[];
    }) => takeRoll(payload),
    onSuccess: invalidate,
  });
}

export function useAttendanceTrend(days = 7) {
  return useQuery({
    queryKey: scheduleKeys.trend(days),
    queryFn: () => fetchAttendanceTrend(days),
    staleTime: 5 * 60_000,
    // The dashboard tile must degrade rather than blank the page when the
    // institution has attendance switched off, or the caller cannot read it.
    retry: false,
  });
}
