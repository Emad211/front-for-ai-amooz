/**
 * The single source of truth for "where does this platform role land after auth".
 * Every redirect site (login form, code-join, auth guard, dashboard layout) must
 * use this so the role→route map can never drift out of sync again.
 *
 * - ADMIN   → /admin   (platform admin panel)
 * - MANAGER → /org     (dedicated org-management panel; a manager is NOT a teacher)
 * - TEACHER → /teacher (teaching panel; freelancer and/or org teacher)
 * - STUDENT → /home
 */
export function landingFor(role: string | null | undefined): string {
  switch ((role || '').toLowerCase()) {
    case 'admin':
      return '/admin';
    case 'manager':
      return '/org';
    case 'teacher':
      return '/teacher';
    default:
      return '/home';
  }
}
