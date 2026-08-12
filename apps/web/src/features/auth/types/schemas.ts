import { z } from 'zod';

/**
 * Login schema factory.
 *
 * It takes a translator so validation messages come from the active locale's
 * dictionary — a schema defined at module scope would freeze whichever language
 * happened to be loaded first.
 */
export function makeLoginSchema(t: (key: string) => string) {
  return z.object({
    email: z
      .string()
      .min(1, t('required'))
      .email(t('invalidEmail')),
    password: z.string().min(1, t('required')),
  });
}

export type LoginFormValues = z.infer<ReturnType<typeof makeLoginSchema>>;
