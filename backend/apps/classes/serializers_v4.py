"""DRF contracts for the feature-gated Exam Prep V4 API."""
from __future__ import annotations

import json
import uuid
from typing import Any

from rest_framework import serializers

from apps.classes.services.exam_prep_v4_uploads import UploadMetadata


class ExamPrepV4UploadMetadataItemSerializer(serializers.Serializer):
    clientRequestId = serializers.UUIDField(required=False, default=uuid.uuid4)
    clientDocumentId = serializers.UUIDField(required=False, default=uuid.uuid4)
    title = serializers.CharField(required=False, allow_blank=True, max_length=255)
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=1000,
    )


class ExamPrepV4BatchUploadControlSerializer(serializers.Serializer):
    organizationId = serializers.IntegerField(required=False, min_value=1)
    studyGroupId = serializers.IntegerField(required=False, min_value=1)


def parse_upload_metadata(raw: Any, *, file_count: int) -> tuple[UploadMetadata, ...]:
    """Parse one optional metadata row per uploaded PDF."""

    if file_count < 1:
        raise serializers.ValidationError({'files': 'حداقل یک فایل PDF لازم است.'})

    if raw in (None, ''):
        rows: Any = [{} for _ in range(file_count)]
    elif isinstance(raw, str):
        try:
            rows = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise serializers.ValidationError(
                {'metadata': 'ساختار metadata معتبر نیست.'}
            ) from exc
    else:
        rows = raw

    if not isinstance(rows, list):
        raise serializers.ValidationError(
            {'metadata': 'metadata باید یک آرایه باشد.'}
        )
    if len(rows) != file_count:
        raise serializers.ValidationError(
            {'metadata': 'برای هر PDF باید دقیقاً یک ردیف metadata وجود داشته باشد.'}
        )

    serializer = ExamPrepV4UploadMetadataItemSerializer(data=rows, many=True)
    serializer.is_valid(raise_exception=True)
    return tuple(
        UploadMetadata(
            client_request_id=item['clientRequestId'],
            client_document_id=item['clientDocumentId'],
            title=str(item.get('title') or '').strip(),
            description=str(item.get('description') or '').strip(),
        )
        for item in serializer.validated_data
    )
