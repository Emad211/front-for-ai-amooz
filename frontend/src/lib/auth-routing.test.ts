/**
 * landingFor() — the role→route map every redirect site shares.
 *
 * Run manually (there is no `npm test` script in this app):
 *   npx tsx --test src/lib/auth-routing.test.ts
 *
 * Guards the S1 landmine: `(dashboard)/layout.tsx` bounces any non-student role
 * through landingFor(). Before ADVISOR was a case here it fell into `default`
 * and returned '/home' — so an advisor logged in, got redirected to the student
 * dashboard, and the /advisor panel was unreachable while looking like the login
 * had worked. A silent failure, hence a test.
 */
import assert from 'node:assert/strict';
import test from 'node:test';

import { landingFor } from './auth-routing';

test('advisor lands on the advisor panel', () => {
  assert.equal(landingFor('ADVISOR'), '/advisor');
  assert.equal(landingFor('advisor'), '/advisor');
});

test('every known role has an explicit route', () => {
  assert.equal(landingFor('ADMIN'), '/admin');
  assert.equal(landingFor('MANAGER'), '/org');
  assert.equal(landingFor('TEACHER'), '/teacher');
  assert.equal(landingFor('PARENT'), '/parent');
  assert.equal(landingFor('STUDENT'), '/home');
});

test('role matching is case-insensitive', () => {
  assert.equal(landingFor('Manager'), '/org');
  assert.equal(landingFor('tEaChEr'), '/teacher');
});

test('unknown, empty and absent roles still fall back to the student home', () => {
  assert.equal(landingFor(''), '/home');
  assert.equal(landingFor(null), '/home');
  assert.equal(landingFor(undefined), '/home');
});
