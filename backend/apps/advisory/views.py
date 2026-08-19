"""Advisory API views.

Step 2 exposes one endpoint: the subject catalog an advisor picks from. It is
read-only — the catalog is curated by a platform admin in Django admin (see
``admin.py``).
"""

from __future__ import annotations

from django.db.models import F, Q
from drf_spectacular.utils import extend_schema
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated

from apps.core.permissions import IsAdvisorUser

from .models import Subject
from .serializers import SubjectSerializer
from .services.scope import advisor_organization_ids


@extend_schema(
    tags=['advisory'],
    summary='فهرست درس‌های قابل انتخاب برای مشاور',
    description=(
        'درس‌های سراسری به‌علاوه‌ی درس‌های خصوصیِ سازمان‌هایی که کاربر در آن‌ها '
        'مشاورِ فعال است. صفحه‌بندی ندارد؛ خروجی یک آرایه‌ی کامل است.'
    ),
    responses={200: SubjectSerializer(many=True)},
)
class SubjectListView(ListAPIView):
    """``GET /api/advisory/subjects/`` — the advisor's subject picker.

    Pagination is switched off deliberately. DRF applies ``PageNumberPagination``
    globally at ``PAGE_SIZE`` (50 by default), and a picker that silently drops
    the 51st subject is a data-entry bug that nobody notices until an advisor
    cannot find a subject that exists. The catalog is small and admin-curated.
    """

    serializer_class = SubjectSerializer
    permission_classes = [IsAuthenticated, IsAdvisorUser]
    pagination_class = None

    def get_queryset(self):
        org_ids = advisor_organization_ids(self.request.user)
        return (
            Subject.objects.filter(is_active=True)
            .filter(Q(organization__isnull=True) | Q(organization_id__in=org_ids))
            .select_related('organization')
            # Globals first, then each organization's own additions. PostgreSQL
            # sorts NULLs last in ASC, so nulls_first has to be explicit.
            .order_by(F('organization_id').asc(nulls_first=True), 'name')
        )
