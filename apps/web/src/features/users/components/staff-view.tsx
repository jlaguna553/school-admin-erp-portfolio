'use client';

import { useTranslations } from 'next-intl';

import { UserList } from './user-list';

/**
 * Every account at the institution, with the role editable.
 *
 * The Students screen is the same list pinned to one role; this one leaves the
 * role open, which is what makes it the place staff are hired, promoted and
 * deactivated. `platform_admin` is absent from the selector because the API
 * only offers roles the caller can actually assign -- see
 * `UserViewSet.roles`.
 */
export function StaffView() {
  const t = useTranslations('users');

  return <UserList title={t('staffTitle')} description={t('staffSubtitle')} />;
}
