import { apiClient } from '@/lib/api-client';
import { createOne, deactivateOne, fetchList, updateOne, type ListParams } from '@/lib/crud';
import type { Assessment, Gradebook, Paginated, Term } from '@erp/api-types';

export const TERMS_PATH = '/api/v1/academic/terms/';
export const ASSESSMENTS_PATH = '/api/v1/academic/assessments/';

// --- Evaluation periods -----------------------------------------------------
export interface TermPayload {
  academic_year: string;
  name: string;
  ordinal: number;
  start_date: string;
  end_date: string;
  is_current: boolean;
}

export const listTerms = (params: ListParams) => fetchList<Term>(TERMS_PATH, params);
export const createTerm = (payload: TermPayload) => createOne<Term>(TERMS_PATH, payload);
export const updateTerm = (id: string, payload: Partial<TermPayload>) =>
  updateOne<Term>(TERMS_PATH, id, payload);
export const deactivateTerm = (id: string) => deactivateOne(TERMS_PATH, id);

export async function listAllTerms(): Promise<Term[]> {
  const { data } = await apiClient.get<Paginated<Term>>(TERMS_PATH, {
    params: { page_size: 100, ordering: 'ordinal' },
  });
  return data.results;
}

// --- Assessments ------------------------------------------------------------
export interface AssessmentPayload {
  subject: string;
  term: string;
  name: string;
  max_score: string;
  weight: string;
  due_date?: string | null;
}

export const createAssessment = (payload: AssessmentPayload) =>
  createOne<Assessment>(ASSESSMENTS_PATH, payload);
export const updateAssessment = (id: string, payload: Partial<AssessmentPayload>) =>
  updateOne<Assessment>(ASSESSMENTS_PATH, id, payload);
export const deactivateAssessment = (id: string) => deactivateOne(ASSESSMENTS_PATH, id);

// --- The grid ---------------------------------------------------------------
export async function fetchGradebook(subject: string, term: string): Promise<Gradebook> {
  const { data } = await apiClient.get<Gradebook>('/api/v1/academic/gradebook/', {
    params: { subject, term },
  });
  return data;
}

export interface GradeEntry {
  enrollment_id: string;
  /** `null` clears the mark — distinct from a mark of zero. */
  score: string | null;
  comment?: string;
}

/**
 * Write a whole column at once.
 *
 * Matches how marking is done — a teacher sits with one exam and goes down the
 * list — and means a dropped connection leaves the column either saved or not,
 * rather than half of it.
 */
export async function recordGrades(assessmentId: string, entries: GradeEntry[]): Promise<void> {
  await apiClient.put(`${ASSESSMENTS_PATH}${assessmentId}/grades/`, entries);
}
