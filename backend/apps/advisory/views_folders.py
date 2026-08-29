"""Advisory student-folder endpoints (risman step 1, گام ۱).

ق۱۱: new module, not views.py. Folders are advisor-internal — there is
deliberately **no** ``me/`` route for them, so the permission split here is
one-sided: ``IsAdvisorUser`` everywhere.

``AdvisorFolderListView``
    ``GET|POST /api/advisory/folders/``
``AdvisorFolderDetailView``
    ``PATCH|DELETE /api/advisory/folders/<folder_id>/``
``AssignEngagementFolderView``
    ``PATCH /api/advisory/students/<pk>/folder/``

Every route resolves ownership before touching the door: a foreign or unknown
folder id is a **404, never a 403** (the S1–S3 convention), and the move route
resolves its engagement through ``scope.advisor_engagement`` exactly like every
other advisor detail route.
"""

from __future__ import annotations

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAdvisorUser

from .serializers import (
    AdvisorFolderSerializer,
    EngagementFolderWriteSerializer,
    FolderWriteSerializer,
)
from .services import folders as folder_service
from .views import _resolve_engagement_or_404


def _folder_error_response(exc: folder_service.FolderError) -> Response:
    """Every FolderError is a well-formed-but-rejected request: 400."""
    return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class AdvisorFolderListView(APIView):
    """The advisor's folder list, and the create door."""

    permission_classes = [IsAuthenticated, IsAdvisorUser]

    @extend_schema(
        tags=['advisory'],
        summary='پوشه‌های دانش‌آموزان مشاور',
        description='پوشه‌های خودِ مشاور، مرتب بر اساس نام؛ پوشهٔ مشاور دیگری هرگز نمی‌آید.',
        responses={200: AdvisorFolderSerializer(many=True)},
    )
    def get(self, request):
        rows = folder_service.list_folders(request.user)
        return Response(AdvisorFolderSerializer(rows, many=True).data)

    @extend_schema(
        tags=['advisory'],
        summary='ساخت پوشهٔ تازه',
        description=(
            'نام الزامی است، حداکثر ۶۴ نویسه، و در میان پوشه‌های خود مشاور '
            'یکتاست؛ تخلف ۴۰۰ با پیام فارسی می‌دهد.'
        ),
        request=FolderWriteSerializer,
        responses={
            201: AdvisorFolderSerializer,
            400: OpenApiResponse(description='نام خالی/بلند/تکراری'),
        },
    )
    def post(self, request):
        serializer = FolderWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            folder = folder_service.create_folder(
                request.user, serializer.validated_data.get('name'),
            )
        except folder_service.FolderError as exc:
            return _folder_error_response(exc)
        return Response(
            AdvisorFolderSerializer(folder).data,
            status=status.HTTP_201_CREATED,
        )


class AdvisorFolderDetailView(APIView):
    """Rename and delete doors for one of the advisor's own folders."""

    permission_classes = [IsAuthenticated, IsAdvisorUser]

    def _resolve(self, request, folder_id: int):
        """Owner-scoped lookup; a miss becomes a 404 response."""
        folder = folder_service.get_folder(request.user, folder_id)
        if folder is None:
            return None, Response(
                {'detail': 'پوشه پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND,
            )
        return folder, None

    @extend_schema(
        tags=['advisory'],
        summary='تغییر نام پوشه',
        description=(
            'همان قواعد ساخت: نام الزامی، ≤۶۴ نویسه، یکتا در میان پوشه‌های '
            'خود مشاور. پوشهٔ مشاور دیگر یا ناموجود ۴۰۴ است.'
        ),
        request=FolderWriteSerializer,
        responses={
            200: AdvisorFolderSerializer,
            400: OpenApiResponse(description='نام خالی/بلند/تکراری'),
            404: OpenApiResponse(description='پوشه پیدا نشد'),
        },
    )
    def patch(self, request, folder_id: int):
        folder, error = self._resolve(request, folder_id)
        if error is not None:
            return error

        serializer = FolderWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            folder = folder_service.rename_folder(
                folder, serializer.validated_data.get('name'),
            )
        except folder_service.FolderError as exc:
            return _folder_error_response(exc)
        return Response(AdvisorFolderSerializer(folder).data)

    @extend_schema(
        tags=['advisory'],
        summary='حذف پوشه',
        description=(
            'حذف پوشه دانش‌آموزان داخلش را حذف نمی‌کند؛ همۀ آن‌ها «بدون پوشه» '
            'می‌شوند. پوشهٔ مشاور دیگر یا ناموجود ۴۰۴ است.'
        ),
        responses={
            204: OpenApiResponse(description='حذف شد'),
            404: OpenApiResponse(description='پوشه پیدا نشد'),
        },
    )
    def delete(self, request, folder_id: int):
        folder, error = self._resolve(request, folder_id)
        if error is not None:
            return error
        folder_service.delete_folder(folder)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AssignEngagementFolderView(APIView):
    """``PATCH /api/advisory/students/<pk>/folder/`` — move one student.

    The body is ``{folderId: <id|null>}``: an id files the engagement into
    that one of the advisor's own folders, ``null`` unfiles it. A foreign or
    unknown engagement answers 404 like every advisor detail route; a foreign
    or unknown folder *id in the body* answers 400 with its Persian message.
    """

    permission_classes = [IsAuthenticated, IsAdvisorUser]

    @extend_schema(
        tags=['advisory'],
        summary='انتقال دانش‌آموز به پوشه (یا خارج کردن از پوشه)',
        description=(
            '`pk` شناسه‌ی همکاری است. بدنه `{folderId}` است؛ `null` یعنی بدون '
            'پوشه. پوشه باید مال خود مشاور باشد وگرنه ۴۰۰.'
        ),
        request=EngagementFolderWriteSerializer,
        responses={
            200: OpenApiResponse(description='{"engagementId": …, "folderId": …|null}'),
            400: OpenApiResponse(description='پوشهٔ نامعتبر'),
            404: OpenApiResponse(description='همکاری پیدا نشد'),
        },
    )
    def patch(self, request, pk: int):
        engagement, error = _resolve_engagement_or_404(request, pk)
        if error is not None:
            return error

        serializer = EngagementFolderWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        raw_folder_id = serializer.validated_data['folderId']

        folder = None
        if raw_folder_id is not None:
            folder = folder_service.get_folder(request.user, raw_folder_id)
            if folder is None:
                return Response(
                    {'detail': 'پوشه انتخابی معتبر نیست.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        folder_service.assign_engagement_folder(engagement, folder)
        return Response({
            'engagementId': engagement.pk,
            'folderId': folder.pk if folder is not None else None,
        })
