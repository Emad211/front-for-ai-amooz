"""Serializers for the advisory API.

Wire shape is camelCase, matching ``organizations`` and ``classes`` — the
frontend consumes these directly with no key mapping layer.
"""

from __future__ import annotations

from rest_framework import serializers

from .models import Subject


class SubjectSerializer(serializers.ModelSerializer):
    """Read-only projection of a catalog subject.

    ``normalized_name`` is deliberately absent: it is an internal duplicate key,
    not information the advisor needs, and exposing it would invite a client to
    start matching on it.
    """

    organizationId = serializers.IntegerField(
        source='organization_id', read_only=True, allow_null=True,
    )
    organizationName = serializers.CharField(
        source='organization.name', read_only=True, default=None,
    )
    isGlobal = serializers.BooleanField(source='is_global', read_only=True)
    isActive = serializers.BooleanField(source='is_active', read_only=True)

    class Meta:
        model = Subject
        fields = [
            'id',
            'name',
            'organizationId',
            'organizationName',
            'isGlobal',
            'isActive',
        ]
        read_only_fields = fields
