"use client";

import { useCallback, useEffect, useRef, useState } from 'react';
import { OrganizationService } from '@/services/organization-service';
import type { Organization, OrgMembership, InvitationCode, OrgDashboard, OrgRole } from '@/types';
import { useMountedRef } from '@/hooks/use-mounted-ref';

// ============================================================================
// useOrganizations — list / CRUD orgs (platform admin)
// ============================================================================

export function useOrganizations() {
  const mountedRef = useMountedRef();
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      setError(null);
      setIsLoading(true);
      const data = await OrganizationService.getOrganizations();
      if (mountedRef.current) setOrganizations(data);
    } catch (err) {
      console.error(err);
      if (mountedRef.current) setError('خطا در دریافت لیست سازمان‌ها');
    } finally {
      if (mountedRef.current) setIsLoading(false);
    }
  }, [mountedRef]);

  useEffect(() => { reload(); }, [reload]);

  return { organizations, isLoading, error, reload };
}

// ============================================================================
// useOrgMembers — list / manage members (org admin)
// ============================================================================

export function useOrgMembers(orgId: number) {
  const mountedRef = useMountedRef();
  const [members, setMembers] = useState<OrgMembership[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [roleFilter, setRoleFilter] = useState<OrgRole | ''>('');
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  // Debounce search input by 300ms
  useEffect(() => {
    debounceRef.current = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(debounceRef.current);
  }, [search]);

  const reload = useCallback(async () => {
    try {
      setError(null);
      setIsLoading(true);
      const data = await OrganizationService.getMembers(orgId, {
        role: roleFilter || undefined,
        search: debouncedSearch || undefined,
      });
      if (mountedRef.current) setMembers(data);
    } catch (err) {
      console.error(err);
      if (mountedRef.current) setError('خطا در دریافت اعضا');
    } finally {
      if (mountedRef.current) setIsLoading(false);
    }
  }, [mountedRef, orgId, roleFilter, debouncedSearch]);

  useEffect(() => { reload(); }, [reload]);

  return { members, isLoading, error, roleFilter, setRoleFilter, search, setSearch, reload };
}

// ============================================================================
// useInvitationCodes — list / manage invitation codes (org admin)
// ============================================================================

export function useInvitationCodes(orgId: number) {
  const mountedRef = useMountedRef();
  const [codes, setCodes] = useState<InvitationCode[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      setError(null);
      setIsLoading(true);
      const data = await OrganizationService.getInvitationCodes(orgId);
      if (mountedRef.current) setCodes(data);
    } catch (err) {
      console.error(err);
      if (mountedRef.current) setError('خطا در دریافت کدهای دعوت');
    } finally {
      if (mountedRef.current) setIsLoading(false);
    }
  }, [mountedRef, orgId]);

  useEffect(() => { reload(); }, [reload]);

  return { codes, isLoading, error, reload };
}

// ============================================================================
// useOrgDashboard — org admin dashboard stats
// ============================================================================

export function useOrgDashboard(orgId: number) {
  const mountedRef = useMountedRef();
  const [dashboard, setDashboard] = useState<OrgDashboard | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      setError(null);
      setIsLoading(true);
      const data = await OrganizationService.getDashboard(orgId);
      if (mountedRef.current) setDashboard(data);
    } catch (err) {
      console.error(err);
      if (mountedRef.current) setError('خطا در دریافت اطلاعات داشبورد');
    } finally {
      if (mountedRef.current) setIsLoading(false);
    }
  }, [mountedRef, orgId]);

  useEffect(() => { reload(); }, [reload]);

  return { dashboard, isLoading, error, reload };
}
