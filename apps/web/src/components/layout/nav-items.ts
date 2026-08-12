import {
  BookOpen,
  Building2,
  CalendarCheck,
  CalendarDays,
  ClipboardList,
  GraduationCap,
  LayoutDashboard,
  Receipt,
  Settings,
  UserCog,
  Users,
  type LucideIcon,
} from 'lucide-react';

import { MODULE, canReadModule, type ModuleKey } from '@/lib/access';

/**
 * Sidebar navigation.
 *
 * The reference design's generic items (Projects, Messages…) are replaced by the
 * ERP's modules, which deliberately mirror the Django bounded contexts — so a
 * screen's URL, its API namespace and its owning app all line up.
 *
 * `labelKey` indexes into the `nav` group of the next-intl dictionaries; nothing
 * here is a display string.
 */
export interface NavItem {
  href: string;
  labelKey: string;
  icon: LucideIcon;
  /**
   * The module this screen belongs to.
   *
   * Two things follow from it: the roles that may read it, and whether the
   * institution has switched it off. Omitted for screens every signed-in person
   * reaches whatever their role -- their own dashboard and their own settings.
   */
  module?: ModuleKey;
}

export const navItems: NavItem[] = [
  { href: '/dashboard', labelKey: 'dashboard', icon: LayoutDashboard },
  // Students are `users` filtered by role, so they answer to the same module.
  { href: '/students', labelKey: 'students', icon: Users, module: MODULE.USERS },
  { href: '/users', labelKey: 'users', icon: UserCog, module: MODULE.USERS },
  { href: '/academic', labelKey: 'academic', icon: GraduationCap, module: MODULE.ACADEMIC },
  { href: '/subjects', labelKey: 'subjects', icon: BookOpen, module: MODULE.SUBJECTS },
  { href: '/grades', labelKey: 'grades', icon: ClipboardList, module: MODULE.GRADES },
  { href: '/schedule', labelKey: 'schedule', icon: CalendarDays, module: MODULE.SCHEDULE },
  { href: '/attendance', labelKey: 'attendance', icon: CalendarCheck, module: MODULE.ATTENDANCE },
  { href: '/billing', labelKey: 'billing', icon: Receipt, module: MODULE.BILLING },
  { href: '/settings', labelKey: 'settings', icon: Settings },
];

/**
 * The platform operator's menu, shown on the public host.
 *
 * A separate list rather than a filtered `navItems`: an operator is not a member
 * of any school, so the school modules have no tenant to run against and every
 * one of those links would fail.
 */
export const platformNavItems: NavItem[] = [
  { href: '/platform', labelKey: 'institutions', icon: Building2 },
  { href: '/platform/people', labelKey: 'people', icon: Users },
  { href: '/users', labelKey: 'platformStaff', icon: UserCog },
];

/**
 * The menu this person actually has.
 *
 * Filtered by both questions the API asks: has the institution switched the
 * module off, and may this role read it. A student is left with their dashboard
 * and their settings, which is the whole of what they administer.
 */
export function visibleNavItems(
  role: string | undefined,
  enabledModules: string[] | undefined,
): NavItem[] {
  return navItems.filter(
    (item) => !item.module || canReadModule(item.module, role, enabledModules),
  );
}
