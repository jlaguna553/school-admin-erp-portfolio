import { apiClient } from '@/lib/api-client';
import {
  createOne,
  deactivateOne,
  fetchList,
  updateOne,
  type ListParams,
} from '@/lib/crud';
import type { AcademicYear, Enrollment, Paginated, Program, Subject } from '@erp/api-types';

export const ACADEMIC_YEARS_PATH = '/api/v1/academic/academic-years/';
export const PROGRAMS_PATH = '/api/v1/academic/programs/';
export const SUBJECTS_PATH = '/api/v1/academic/subjects/';
export const ENROLLMENTS_PATH = '/api/v1/academic/enrollments/';

// --- Academic years ---------------------------------------------------------
export interface AcademicYearPayload {
  name: string;
  start_date: string;
  end_date: string;
  is_current: boolean;
}

export const listAcademicYears = (params: ListParams) =>
  fetchList<AcademicYear>(ACADEMIC_YEARS_PATH, params);

export const createAcademicYear = (payload: AcademicYearPayload) =>
  createOne<AcademicYear>(ACADEMIC_YEARS_PATH, payload);

export const updateAcademicYear = (id: string, payload: Partial<AcademicYearPayload>) =>
  updateOne<AcademicYear>(ACADEMIC_YEARS_PATH, id, payload);

export const deactivateAcademicYear = (id: string) =>
  deactivateOne(ACADEMIC_YEARS_PATH, id);

// --- Programmes -------------------------------------------------------------
/**
 * Programmes carry translated `name`/`description`.
 *
 * The list endpoint returns them already resolved for the request language, but
 * an editor has to see and write **every** language — hence the
 * `?translations=all` variant, which exposes the raw `name_es` / `name_en`
 * columns instead of the resolved value.
 */
export interface ProgramTranslations {
  id: string;
  code: string;
  name_es: string;
  name_en: string;
  description_es: string;
  description_en: string;
}

export type ProgramPayload = Omit<ProgramTranslations, 'id'>;

export const listPrograms = (params: ListParams) =>
  fetchList<Program>(PROGRAMS_PATH, params);

export async function listAllPrograms(): Promise<Program[]> {
  // Selector options: one page large enough to hold a school's programmes.
  const { data } = await apiClient.get<Paginated<Program>>(PROGRAMS_PATH, {
    params: { page_size: 200, ordering: 'code' },
  });
  return data.results;
}

export async function getProgramTranslations(id: string): Promise<ProgramTranslations> {
  const { data } = await apiClient.get<ProgramTranslations>(`${PROGRAMS_PATH}${id}/`, {
    params: { translations: 'all' },
  });
  return data;
}

export async function createProgram(payload: ProgramPayload): Promise<ProgramTranslations> {
  const { data } = await apiClient.post<ProgramTranslations>(PROGRAMS_PATH, payload, {
    params: { translations: 'all' },
  });
  return data;
}

export async function updateProgram(
  id: string,
  payload: Partial<ProgramPayload>,
): Promise<ProgramTranslations> {
  const { data } = await apiClient.patch<ProgramTranslations>(
    `${PROGRAMS_PATH}${id}/`,
    payload,
    { params: { translations: 'all' } },
  );
  return data;
}

export const deactivateProgram = (id: string) => deactivateOne(PROGRAMS_PATH, id);

// --- Subjects ---------------------------------------------------------------
export interface SubjectPayload {
  code: string;
  name: string;
  description?: string;
  credits: number;
  program: string;
  teacher?: string | null;
}

export const listSubjects = (params: ListParams) =>
  fetchList<Subject>(SUBJECTS_PATH, params);

export const createSubject = (payload: SubjectPayload) =>
  createOne<Subject>(SUBJECTS_PATH, payload);

export const updateSubject = (id: string, payload: Partial<SubjectPayload>) =>
  updateOne<Subject>(SUBJECTS_PATH, id, payload);

export const deactivateSubject = (id: string) => deactivateOne(SUBJECTS_PATH, id);

// --- Enrollments ------------------------------------------------------------
export interface EnrollmentPayload {
  student: string;
  program: string;
  academic_year: string;
  status: string;
  enrolled_on: string;
}

export const listEnrollments = (params: ListParams) =>
  fetchList<Enrollment>(ENROLLMENTS_PATH, params);

export const createEnrollment = (payload: EnrollmentPayload) =>
  createOne<Enrollment>(ENROLLMENTS_PATH, payload);

export const updateEnrollment = (id: string, payload: Partial<EnrollmentPayload>) =>
  updateOne<Enrollment>(ENROLLMENTS_PATH, id, payload);

export const deactivateEnrollment = (id: string) => deactivateOne(ENROLLMENTS_PATH, id);

/**
 * Students available to enrol, as selector options.
 *
 * A plain `users?role=student` list: enrolment is the academic context's own
 * record *about* a student, and identity stays in the users context.
 */
export async function listStudentOptions(): Promise<
  { id: string; full_name: string; email: string }[]
> {
  const { data } = await apiClient.get<Paginated<{ id: string; full_name: string; email: string }>>(
    '/api/v1/users/',
    { params: { role: 'student', page_size: 200, ordering: 'last_name' } },
  );
  return data.results;
}

export async function listAllAcademicYears(): Promise<AcademicYear[]> {
  const { data } = await apiClient.get<Paginated<AcademicYear>>(ACADEMIC_YEARS_PATH, {
    params: { page_size: 200, ordering: '-start_date' },
  });
  return data.results;
}
