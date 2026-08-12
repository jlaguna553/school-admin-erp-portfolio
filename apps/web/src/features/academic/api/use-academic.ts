'use client';

import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query';

import type { ListParams } from '@/lib/crud';

import {
  createAcademicYear,
  createEnrollment,
  createProgram,
  createSubject,
  deactivateAcademicYear,
  deactivateEnrollment,
  deactivateProgram,
  deactivateSubject,
  getProgramTranslations,
  listAcademicYears,
  listAllAcademicYears,
  listAllPrograms,
  listEnrollments,
  listPrograms,
  listStudentOptions,
  listSubjects,
  updateAcademicYear,
  updateEnrollment,
  updateProgram,
  updateSubject,
  type AcademicYearPayload,
  type EnrollmentPayload,
  type ProgramPayload,
  type SubjectPayload,
} from './academic-api';

export const academicKeys = {
  all: ['academic'] as const,
  years: (params: ListParams) => ['academic', 'years', params] as const,
  programs: (params: ListParams) => ['academic', 'programs', params] as const,
  programOptions: ['academic', 'program-options'] as const,
  programTranslations: (id: string) => ['academic', 'program', id, 'translations'] as const,
  subjects: (params: ListParams) => ['academic', 'subjects', params] as const,
  enrollments: (params: ListParams) => ['academic', 'enrollments', params] as const,
};

function useInvalidateAcademic() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: academicKeys.all });
}

// --- Academic years ---------------------------------------------------------
export function useAcademicYears(params: ListParams) {
  return useQuery({
    queryKey: academicKeys.years(params),
    queryFn: () => listAcademicYears(params),
    placeholderData: keepPreviousData,
  });
}

export function useCreateAcademicYear() {
  const invalidate = useInvalidateAcademic();
  return useMutation({
    mutationFn: (payload: AcademicYearPayload) => createAcademicYear(payload),
    onSuccess: invalidate,
  });
}

export function useUpdateAcademicYear() {
  const invalidate = useInvalidateAcademic();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<AcademicYearPayload> }) =>
      updateAcademicYear(id, payload),
    onSuccess: invalidate,
  });
}

export function useDeactivateAcademicYear() {
  const invalidate = useInvalidateAcademic();
  return useMutation({
    mutationFn: (id: string) => deactivateAcademicYear(id),
    onSuccess: invalidate,
  });
}

// --- Programmes -------------------------------------------------------------
export function usePrograms(params: ListParams) {
  return useQuery({
    queryKey: academicKeys.programs(params),
    queryFn: () => listPrograms(params),
    placeholderData: keepPreviousData,
  });
}

export function useProgramOptions() {
  return useQuery({
    queryKey: academicKeys.programOptions,
    queryFn: listAllPrograms,
    staleTime: 5 * 60_000,
  });
}

export function useProgramTranslations(id: string | null) {
  return useQuery({
    queryKey: academicKeys.programTranslations(id ?? 'none'),
    queryFn: () => getProgramTranslations(id as string),
    enabled: Boolean(id),
  });
}

export function useCreateProgram() {
  const invalidate = useInvalidateAcademic();
  return useMutation({
    mutationFn: (payload: ProgramPayload) => createProgram(payload),
    onSuccess: invalidate,
  });
}

export function useUpdateProgram() {
  const invalidate = useInvalidateAcademic();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<ProgramPayload> }) =>
      updateProgram(id, payload),
    onSuccess: invalidate,
  });
}

export function useDeactivateProgram() {
  const invalidate = useInvalidateAcademic();
  return useMutation({
    mutationFn: (id: string) => deactivateProgram(id),
    onSuccess: invalidate,
  });
}

// --- Subjects ---------------------------------------------------------------
export function useSubjects(params: ListParams) {
  return useQuery({
    queryKey: academicKeys.subjects(params),
    queryFn: () => listSubjects(params),
    placeholderData: keepPreviousData,
  });
}

export function useCreateSubject() {
  const invalidate = useInvalidateAcademic();
  return useMutation({
    mutationFn: (payload: SubjectPayload) => createSubject(payload),
    onSuccess: invalidate,
  });
}

export function useUpdateSubject() {
  const invalidate = useInvalidateAcademic();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<SubjectPayload> }) =>
      updateSubject(id, payload),
    onSuccess: invalidate,
  });
}

export function useDeactivateSubject() {
  const invalidate = useInvalidateAcademic();
  return useMutation({
    mutationFn: (id: string) => deactivateSubject(id),
    onSuccess: invalidate,
  });
}

// --- Enrollments ------------------------------------------------------------
export function useEnrollments(params: ListParams) {
  return useQuery({
    queryKey: academicKeys.enrollments(params),
    queryFn: () => listEnrollments(params),
    placeholderData: keepPreviousData,
  });
}

export function useStudentOptions() {
  return useQuery({
    queryKey: [...academicKeys.all, 'student-options'] as const,
    queryFn: listStudentOptions,
    staleTime: 60_000,
  });
}

export function useAllAcademicYears() {
  return useQuery({
    queryKey: [...academicKeys.all, 'year-options'] as const,
    queryFn: listAllAcademicYears,
    staleTime: 60_000,
  });
}

export function useAllPrograms() {
  return useQuery({
    queryKey: [...academicKeys.all, 'program-options'] as const,
    queryFn: listAllPrograms,
    staleTime: 60_000,
  });
}

export function useCreateEnrollment() {
  const invalidate = useInvalidateAcademic();
  return useMutation({
    mutationFn: (payload: EnrollmentPayload) => createEnrollment(payload),
    onSuccess: invalidate,
  });
}

export function useUpdateEnrollment() {
  const invalidate = useInvalidateAcademic();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<EnrollmentPayload> }) =>
      updateEnrollment(id, payload),
    onSuccess: invalidate,
  });
}

export function useDeactivateEnrollment() {
  const invalidate = useInvalidateAcademic();
  return useMutation({
    mutationFn: (id: string) => deactivateEnrollment(id),
    onSuccess: invalidate,
  });
}
