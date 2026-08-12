/**
 * Hand-written aliases over the generated OpenAPI schemas.
 *
 * One document, because one hostname serves the whole platform. School routes
 * and platform routes share a URLconf, and permissions -- not the host -- decide
 * who reaches which.
 *
 * `schema.d.ts` is generated -- never edit it. Regenerate the contract with:
 *
 *   pnpm --filter @erp/api       run schema   # Django -> openapi.yaml
 *   pnpm --filter @erp/api-types run generate # yaml   -> schema.d.ts
 *
 * The aliases below exist so feature code imports `User` rather than
 * `components['schemas']['User']`, and so a rename in the API surfaces as a
 * type error here (one place) instead of in every consumer.
 */

import type { components, paths } from './schema.js';

export type { components, paths };

export type Schemas = components['schemas'];

// --- Identity ---------------------------------------------------------------
export type User = Schemas['User'];
export type Me = Schemas['Me'];
export type UserRole = Me['role'];

// --- Auth -------------------------------------------------------------------
export type LoginRequest = Schemas['LoginRequest'];
export type LogoutRequest = Schemas['LogoutRequest'];

/**
 * Response of `POST /api/v1/auth/refresh/`.
 *
 * Hand-written because the endpoint takes no request body and declares no
 * response serializer: the refresh token travels as an httpOnly cookie, so there
 * is nothing for drf-spectacular to infer a schema from.
 */
export interface TokenRefreshResponse {
  access: string;
  /** Only when the server runs with `AUTH_REFRESH_IN_BODY=True`. */
  refresh?: string;
}

/**
 * Response body of `POST /api/v1/auth/login/`.
 *
 * Written by hand on purpose: SimpleJWT's view has no response serializer, so
 * drf-spectacular can only describe the *request*. Keep this in step with
 * `TenantTokenObtainPairSerializer.validate`.
 */
export interface LoginResponse {
  access: string;
  /**
   * Absent for browser clients: the refresh token is delivered as an httpOnly
   * cookie so JavaScript cannot read it. Only present when the server runs with
   * `AUTH_REFRESH_IN_BODY=True`, for native clients that cannot use cookies.
   */
  refresh?: string;
  user: {
    id: string;
    email: string;
    full_name: string;
    role: string;
    roles: string[];
    language: string;
  };
  tenant: {
    id: string | null;
    schema: string;
    name: string | null;
    default_language: string | null;
    /** Every invoice this institution issues is denominated in it. */
    default_currency: Currency | null;
    /** The palette is derived from this; see `lib/brand.ts`. */
    brand_color: string | null;
    /**
     * What this institution actually runs.
     *
     * The interface hides what is switched off rather than offering screens the
     * API will refuse with `module_disabled`.
     */
    modules: string[];
  };
  /**
   * Every school this account may work at, current one included.
   *
   * The school is no longer chosen by hostname, so the client needs the list to
   * render a switcher — and one entry means no switcher at all, which is the
   * common case. Empty for a platform operator.
   */
  schools: AvailableSchool[];
}

/** Claims this project adds to the SimpleJWT access token. */
export interface AccessTokenClaims {
  token_type: 'access';
  exp: number;
  iat: number;
  jti: string;
  user_id: string;
  tenant_schema: string;
  tenant_id: string | null;
  tenant_name: string | null;
  /**
   * The institution's billing currency. Carried in the token so a reload can
   * format amounts immediately: a refresh returns only an access token, with no
   * `tenant` payload to read it from.
   */
  tenant_currency: Currency | null;
  /**
   * The institution's brand colour. In the token because a reload restores the
   * session from the refresh cookie alone, and the interface has to repaint
   * before any request comes back.
   */
  brand_color: string | null;
  /** Enabled modules, in the token so a reload renders the right navigation. */
  modules?: string[];
  roles: string[];
  email: string;
  language: string;
}

/** Currencies the platform bills in. Mirrors `apps.tenants.models.Currency`. */
export type Currency = 'MXN' | 'USD';

// --- Academic ---------------------------------------------------------------
export type Program = Schemas['Program'];
export type Subject = Schemas['Subject'];
export type AcademicYear = Schemas['AcademicYear'];
export type Enrollment = Schemas['Enrollment'];
export type Term = Schemas['Term'];
export type Assessment = Schemas['Assessment'];
export type Gradebook = Schemas['Gradebook'];
export type StudentGroup = Schemas['StudentGroup'];
export type TimetableSlot = Schemas['TimetableSlot'];
export type ClassSession = Schemas['ClassSession'];
/** A register: one class, one date, everyone who should be in the room. */
export type Roll = Schemas['Roll'];
export type RollRow = Schemas['RollRow'];
export type AttendanceStatus = Schemas['AttendanceStatusEnum'];
export type AttendancePoint = Schemas['AttendancePoint'];

// --- Billing ----------------------------------------------------------------
export type Invoice = Schemas['Invoice'];
export type Payment = Schemas['Payment'];

// --- Tenants (platform-operator API; permission-gated, not host-gated) -----
export type Institution = Schemas['Client'];
export type InstitutionProvision = Schemas['ClientProvisionRequest'];
export type InstitutionDomain = Schemas['Domain'];

// --- Cross-school identity (platform API; permission-gated) ----------------
export type PlatformIdentity = Schemas['PlatformIdentity'];
export type Membership = Schemas['Membership'];

/**
 * One entry of `GET /api/v1/auth/schools/`, and of the login response's
 * `schools` array.
 *
 * Carries the school's currency and colour so switching can repaint the
 * interface without a second round trip. Switching is a token re-issue on the
 * same origin, not a navigation -- there is only one origin now.
 */
export type AvailableSchool = Schemas['AvailableSchool'];

// --- Shared envelopes -------------------------------------------------------
/** The single error shape produced by `apps.core.exceptions`. */
export interface ApiError {
  error: {
    code: string;
    message: string;
    details?: Record<string, string[] | string>;
  };
}

/** `apps.core.pagination.DefaultPagination`'s response shape. */
export interface Paginated<T> {
  count: number;
  total_pages: number;
  page: number;
  page_size: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
