"""The only door to tenancy-bearing advisory data.

The repository's existing pattern is a hand-rolled ``IsOrgAdmin.check(...)`` call
repeated at ~19 call sites in ``organizations``. One forgotten call there is one
cross-tenant leak. Advisory does not repeat that: every view asks this module for
a queryset that is *already* scoped, and a guard test (``test_import_boundaries``)
keeps advisory models from being imported anywhere else.

Step 2 only needs the organization gate. ``visible_engagements`` / ``visible_logs``
/ ``visible_plans`` land in steps 3, 5 and 7 alongside their models.
"""

from __future__ import annotations

from apps.organizations.models import Organization, OrganizationMembership


def advisor_organization_ids(user) -> list[int]:
    """Return the organizations whose private data this advisor may see.

    Three conditions, all live (no cached column, no denormalized flag):

    1. the membership row exists and is ``ACTIVE`` — a suspended advisor loses
       access the moment the manager suspends them, with no signal to fire;
    2. its ``org_role`` is ``advisor`` — being a *student* or *teacher* of an
       organization grants no advisory visibility;
    3. the organization's subscription is ``ACTIVE`` — an expired org goes dark
       for the same reason it does everywhere else in the platform.

    Membership rows are hard-deleted on removal (``organizations/views.py``), so
    checking them live is the only reliable gate — see C1 in the spec.
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return []
    return list(
        OrganizationMembership.objects.filter(
            user=user,
            org_role=OrganizationMembership.OrgRole.ADVISOR,
            status=OrganizationMembership.MemberStatus.ACTIVE,
            organization__subscription_status=Organization.SubscriptionStatus.ACTIVE,
        )
        .values_list('organization_id', flat=True)
        .distinct()
    )
