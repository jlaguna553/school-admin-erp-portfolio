'use client';

import { useTranslations } from 'next-intl';

import { UserList } from './user-list';

/**
 * Students are `users` filtered to `role=student`, not a separate resource.
 * Enrollment (which programme, which year) lives in the academic context.
 */
export function StudentsView() {
  const t = useTranslations('users');

  return (
    <UserList
      role="student"
      title={t('studentsTitle')}
      description={t('studentsSubtitle')}
    />
  );
}
