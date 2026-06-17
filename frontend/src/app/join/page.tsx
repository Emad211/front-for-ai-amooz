import { redirect } from 'next/navigation';

/**
 * Legacy route. Joining an organization with a code is now unified under
 * /join-code (one smart code page that detects org vs class codes). Redirect to
 * keep old links alive.
 */
export default function JoinRedirect() {
  redirect('/join-code');
}
