import { apiClient } from '@/lib/api-client';
import { createOne, deactivateOne, fetchList, updateOne, type ListParams } from '@/lib/crud';
import type {
  AttendancePoint,
  AttendanceStatus,
  Paginated,
  Roll,
  StudentGroup,
  TimetableSlot,
} from '@erp/api-types';

export const GROUPS_PATH = '/api/v1/academic/groups/';
export const TIMETABLE_PATH = '/api/v1/academic/timetable/';
export const ROLL_PATH = '/api/v1/academic/roll/';
export const TODAY_CLASSES_PATH = '/api/v1/academic/classes/today/';
export const ATTENDANCE_TREND_PATH = '/api/v1/academic/attendance/weekly/';

// --- Groups -----------------------------------------------------------------
export interface GroupPayload {
  name: string;
  program: string;
  academic_year: string;
  tutor?: string | null;
  room?: string;
}

export const listGroups = (params: ListParams) => fetchList<StudentGroup>(GROUPS_PATH, params);

export const createGroup = (payload: GroupPayload) => createOne<StudentGroup>(GROUPS_PATH, payload);

export const updateGroup = (id: string, payload: Partial<GroupPayload>) =>
  updateOne<StudentGroup>(GROUPS_PATH, id, payload);

export const deactivateGroup = (id: string) => deactivateOne(GROUPS_PATH, id);

/** Selector options: one page large enough to hold a school's sections. */
export async function listAllGroups(): Promise<StudentGroup[]> {
  const { data } = await apiClient.get<Paginated<StudentGroup>>(GROUPS_PATH, {
    params: { page_size: 200 },
  });
  return data.results;
}

// --- Timetable --------------------------------------------------------------
export interface SlotPayload {
  group: string;
  subject: string;
  weekday: number;
  start_time: string;
  end_time: string;
  room?: string;
}

export const createSlot = (payload: SlotPayload) => createOne<TimetableSlot>(TIMETABLE_PATH, payload);

export const updateSlot = (id: string, payload: Partial<SlotPayload>) =>
  updateOne<TimetableSlot>(TIMETABLE_PATH, id, payload);

export const deactivateSlot = (id: string) => deactivateOne(TIMETABLE_PATH, id);

/**
 * A whole week of classes, unpaginated.
 *
 * The grid is only readable complete: a page boundary in the middle of a week
 * would draw Thursday's lessons into an empty Friday. A school week is a couple
 * of hundred rows at most, so it is one request.
 */
export async function fetchWeek(filters: {
  group?: string;
  teacher?: string;
}): Promise<TimetableSlot[]> {
  const { data } = await apiClient.get<Paginated<TimetableSlot>>(TIMETABLE_PATH, {
    params: { ...filters, page_size: 500, ordering: 'start_time' },
  });
  return data.results;
}

// --- Attendance -------------------------------------------------------------
export interface RollEntry {
  enrollment_id: string;
  status: AttendanceStatus | null;
  note?: string;
}

export async function fetchRoll(slot: string, date: string): Promise<Roll> {
  const { data } = await apiClient.get<Roll>(ROLL_PATH, { params: { slot, date } });
  return data;
}

export async function takeRoll(payload: {
  slot: string;
  date: string;
  status?: 'held' | 'cancelled';
  note?: string;
  entries: RollEntry[];
}): Promise<Roll> {
  const { data } = await apiClient.put<Roll>(ROLL_PATH, { status: 'held', ...payload });
  return data;
}

/** The day's classes with whether each register has been taken. */
export async function fetchDayClasses(params: {
  date: string;
  teacher?: string;
  group?: string;
}): Promise<Roll[]> {
  const { data } = await apiClient.get<Roll[]>(TODAY_CLASSES_PATH, { params });
  return data;
}

export async function fetchAttendanceTrend(days = 7): Promise<AttendancePoint[]> {
  const { data } = await apiClient.get<AttendancePoint[]>(ATTENDANCE_TREND_PATH, {
    params: { days },
  });
  return data;
}
