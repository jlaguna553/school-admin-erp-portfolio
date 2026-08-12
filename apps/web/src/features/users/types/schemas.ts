import { z } from 'zod';

type Translate = (key: string) => string;

/**
 * User form schema.
 *
 * `password` is required when creating and omitted when editing — the API has
 * no "change someone else's password" endpoint, so edit forms must not send it.
 */
export function makeUserSchema(t: Translate, mode: 'create' | 'edit') {
  const base = z.object({
    email: z.string().min(1, t('required')).email(t('invalidEmail')),
    first_name: z.string().min(1, t('required')).max(150),
    last_name: z.string().min(1, t('required')).max(150),
    phone: z.string().max(32).optional().or(z.literal('')),
    role: z.string().min(1, t('required')),
    language: z.enum(['es', 'en']),
  });

  if (mode === 'edit') {
    return base.extend({ password: z.string().optional() });
  }

  return base.extend({
    password: z.string().min(8, t('passwordTooShort')),
  });
}

export type UserFormValues = z.infer<ReturnType<typeof makeUserSchema>>;
