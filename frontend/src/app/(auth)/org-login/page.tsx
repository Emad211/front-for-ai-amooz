import { redirect } from 'next/navigation';

/**
 * Legacy route. Org sign-in/join is now unified under /join-code (one smart
 * code page that detects org vs class codes). Redirect to keep old links alive.
 */
export default function OrgLoginRedirect() {
  redirect('/join-code');
}
