import { z } from 'zod';

type Translate = (key: string) => string;

/**
 * Institution form schema.
 *
 * The same shape for both modes: opening a school asks for nothing an operator
 * would have to invent. The Postgres schema is derived from the name by the
 * API, and there is no hostname, because one domain serves every school -- which
 * one a request is for comes from whoever signed in.
 */
export function makeInstitutionSchema(t: Translate) {
  return z.object({
    name: z.string().min(1, t('required')).max(200),
    legal_name: z.string().max(255).optional().or(z.literal('')),
    tax_id: z.string().max(50).optional().or(z.literal('')),
    default_language: z.enum(['es', 'en']),
    default_currency: z.enum(['MXN', 'USD']),
    // Mirrors the API's own validator. The rest of the palette is derived from
    // this one value, so there is no combination an operator can pick that
    // renders unreadable text.
    brand_color: z.string().regex(/^#[0-9a-fA-F]{6}$/, t('invalidColor')),
    timezone: z.string().max(64).optional().or(z.literal('')),
    // What the institution has switched *off*. Stored as the exception so a
    // module shipped later is live everywhere without a data migration.
    disabled_modules: z.array(z.string()),
  });
}

/**
 * Inferred, now that the form has a single shape.
 *
 * It was written by hand while `makeInstitutionSchema` returned one of two --
 * inferring across that union collapsed to the narrower one. The copy then
 * drifted: it still carried a `schema_name` the API derives and knew nothing of
 * the module toggles, which is the failure mode a hand-maintained mirror always
 * has.
 */
export type InstitutionFormValues = z.infer<ReturnType<typeof makeInstitutionSchema>>;
