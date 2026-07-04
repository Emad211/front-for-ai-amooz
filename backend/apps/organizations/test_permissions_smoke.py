"""Organization platform-admin permission matrix — built on the shared fixtures
(ADR-0003, T3 proof of cross-app fixture adoption; real value: org-CRUD authz).

`/api/organizations/` (OrganizationListCreateView) is platform-admin only
(`IsPlatformAdmin`, which counts is_staff/is_superuser as admin). MANAGER is
org-oversight — NOT a platform admin — so it must be forbidden here too.
"""
import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.permission]


class TestOrganizationListPermissions:
    URL = '/api/organizations/'

    def test_anonymous_rejected(self, anon_client):
        assert anon_client.get(self.URL).status_code == 401

    def test_teacher_forbidden(self, teacher_client):
        assert teacher_client.get(self.URL).status_code == 403

    def test_student_forbidden(self, student_client):
        assert student_client.get(self.URL).status_code == 403

    def test_manager_forbidden(self, manager_client):
        # MANAGER manages an org but is not a platform admin — no org-CRUD access.
        assert manager_client.get(self.URL).status_code == 403

    def test_admin_allowed(self, admin_client):
        assert admin_client.get(self.URL).status_code == 200
