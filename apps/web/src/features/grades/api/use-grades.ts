'use client';

import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type { ListParams } from '@/lib/crud';

import {
  createAssessment,
  createTerm,
  deactivateAssessment,
  deactivateTerm,
  fetchGradebook,
  listAllTerms,
  listTerms,
  recordGrades,
  updateTerm,
  type AssessmentPayload,
  type GradeEntry,
  type TermPayload,
} from './grades-api';

export const gradeKeys = {
  all: ['grades'] as const,
  terms: (params: ListParams) => ['grades', 'terms', params] as const,
  termOptions: ['grades', 'term-options'] as const,
  gradebook: (subject: string, term: string) => ['grades', 'gradebook', subject, term] as const,
};

export function useTerms(params: ListParams) {
  return useQuery({
    queryKey: gradeKeys.terms(params),
    queryFn: () => listTerms(params),
    placeholderData: keepPreviousData,
  });
}

export function useTermOptions() {
  return useQuery({
    queryKey: gradeKeys.termOptions,
    queryFn: listAllTerms,
    staleTime: 60_000,
  });
}

function useInvalidateGrades() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: gradeKeys.all });
}

export function useCreateTerm() {
  const invalidate = useInvalidateGrades();
  return useMutation({ mutationFn: (p: TermPayload) => createTerm(p), onSuccess: invalidate });
}

export function useUpdateTerm() {
  const invalidate = useInvalidateGrades();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<TermPayload> }) =>
      updateTerm(id, payload),
    onSuccess: invalidate,
  });
}

export function useDeactivateTerm() {
  const invalidate = useInvalidateGrades();
  return useMutation({ mutationFn: (id: string) => deactivateTerm(id), onSuccess: invalidate });
}

export function useGradebook(subject: string, term: string) {
  return useQuery({
    queryKey: gradeKeys.gradebook(subject, term),
    queryFn: () => fetchGradebook(subject, term),
    enabled: Boolean(subject && term),
    placeholderData: keepPreviousData,
  });
}

export function useCreateAssessment() {
  const invalidate = useInvalidateGrades();
  return useMutation({
    mutationFn: (p: AssessmentPayload) => createAssessment(p),
    onSuccess: invalidate,
  });
}

export function useDeactivateAssessment() {
  const invalidate = useInvalidateGrades();
  return useMutation({
    mutationFn: (id: string) => deactivateAssessment(id),
    onSuccess: invalidate,
  });
}

export function useRecordGrades() {
  const invalidate = useInvalidateGrades();
  return useMutation({
    mutationFn: ({ assessmentId, entries }: { assessmentId: string; entries: GradeEntry[] }) =>
      recordGrades(assessmentId, entries),
    onSuccess: invalidate,
  });
}
