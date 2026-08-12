import type { AccessTokenClaims } from '@erp/api-types';

/**
 * What the interface may show.
 *
 * A mirror of the API's rules, and only ever a mirror: every one of these is
 * re-checked server-side, because a decision taken in the browser is a decision
 * taken by whoever controls the browser. What this buys is honesty — screens a
 * person cannot use are not offered, instead of rendering a console whose every
 * button returns 403.
 *
 * Kept in step with `apps/core/modules.py` and `apps/core/roles.py` by hand.
 * The alternative — serving the matrix from the API — would be one more request
 * before the first paint to describe rules the server enforces anyway.
 */

export type Role =
  | 'platform_admin'
  | 'school_admin'
  | 'coordinator'
  | 'accountant'
  | 'teacher'
  | 'guardian'
  | 'student';

export const ADMINISTRATION: Role[] = ['school_admin', 'coordinator'];
export const FINANCE: Role[] = ['school_admin', 'accountant'];
export const TEACHING: Role[] = ['school_admin', 'coordinator', 'teacher'];

/** Modules, matching `apps.core.modules.Module`. */
export const MODULE = {
  USERS: 'users',
  ACADEMIC: 'academic',
  SUBJECTS: 'subjects',
  GRADES: 'grades',
  BILLING: 'billing',
  SCHEDULE: 'schedule',
  ATTENDANCE: 'attendance',
} as const;

export type ModuleKey = (typeof MODULE)[keyof typeof MODULE];

/** Who may *read* each module. Writing is narrower and the API decides it. */
export const MODULE_READERS: Record<ModuleKey, Role[]> = {
  [MODULE.USERS]: ADMINISTRATION,
  [MODULE.ACADEMIC]: TEACHING,
  [MODULE.SUBJECTS]: TEACHING,
  // The one module teachers write; the API narrows it to their own subjects.
  [MODULE.GRADES]: TEACHING,
  // The one that shows reach is not rank: an accountant ranks below a
  // coordinator and is the only one of the two who belongs here.
  [MODULE.BILLING]: FINANCE,
  [MODULE.SCHEDULE]: TEACHING,
  // Written by teachers too, and narrowed by the API to the classes they teach.
  [MODULE.ATTENDANCE]: TEACHING,
};

/**
 * Modules an institution may switch off.
 *
 * `users` is absent on purpose: a school with no way to manage its people is a
 * school nobody can administer, including whoever switched it off.
 */
export const OPTIONAL_MODULES: ModuleKey[] = [
  MODULE.ACADEMIC,
  MODULE.SUBJECTS,
  MODULE.GRADES,
  MODULE.BILLING,
  MODULE.SCHEDULE,
  MODULE.ATTENDANCE,
];

/**
 * Modules that are useless without another one.
 *
 * Attendance is taken against a timetabled class, so switching off the schedule
 * switches this off too. The API computes the same thing and is the authority —
 * `enabled_modules` already arrives with the dependency applied. This mirror
 * exists for the operator's console, which has to explain *why* a switch it did
 * not touch has gone dark.
 */
export const MODULE_REQUIRES: Partial<Record<ModuleKey, ModuleKey>> = {
  [MODULE.ATTENDANCE]: MODULE.SCHEDULE,
};

export function isPlatformOperator(claims: AccessTokenClaims | null): boolean {
  // The schema, not just the role: an operator works above every institution,
  // which is exactly what being on `public` means.
  return claims?.tenant_schema === 'public';
}

export function canReadModule(
  module: ModuleKey,
  role: string | undefined,
  enabledModules: string[] | undefined,
): boolean {
  // Switched off for this institution: refused to everyone, its administrator
  // included. "Off for most people" is not a setting anyone can reason about.
  if (enabledModules && !enabledModules.includes(module)) return false;
  return MODULE_READERS[module].includes(role as Role);
}
