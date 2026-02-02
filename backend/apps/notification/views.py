from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from apps.accounts.models import User
from apps.classes.permissions import IsTeacherUser
from .models import AdminNotification
from .permissions import IsAdminUser
from .serializers import (
    AdminNotificationCreateSerializer,
    AdminNotificationSerializer,
    UserRecipientSerializer,
)


class AdminNotificationBroadcastView(APIView):
    """Create a broadcast notification by admin."""

    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        tags=['Notifications'],
        summary='Create admin broadcast notification',
        operation_id='admin_notifications_broadcast',
        request=AdminNotificationCreateSerializer,
        responses={201: AdminNotificationSerializer},
    )
    def post(self, request):
        serializer = AdminNotificationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        notification = AdminNotification.objects.create(
            title=data['title'],
            message=data['message'],
            notification_type=data.get('notification_type', AdminNotification.NotificationType.INFO),
            audience=data.get('audience', AdminNotification.Audience.ALL),
            created_by=request.user,
        )
        return Response(AdminNotificationSerializer(notification).data, status=status.HTTP_201_CREATED)


class AdminNotificationRecipientsView(APIView):
    """List potential recipients (students and teachers) for admin broadcast UI."""

    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        tags=['Notifications'],
        summary='List recipients for admin notifications',
        operation_id='admin_notifications_recipients',
        responses={200: UserRecipientSerializer(many=True)},
    )
    def get(self, request):
        qs = User.objects.filter(role__in=[User.Role.STUDENT, User.Role.TEACHER]).order_by('id')
        return Response(UserRecipientSerializer(qs, many=True).data)


class TeacherNotificationListView(APIView):
    """List admin notifications for teachers."""

    permission_classes = [IsAuthenticated, IsTeacherUser]

    @extend_schema(
        tags=['Notifications'],
        summary='List teacher notifications (admin broadcasts)',
        operation_id='teacher_notifications_list',
        responses={200: AdminNotificationSerializer(many=True)},
    )
    def get(self, request):
        qs = AdminNotification.objects.filter(
            audience__in=[AdminNotification.Audience.ALL, AdminNotification.Audience.TEACHERS],
        ).order_by('-created_at')

        out = [
            {
                'id': f'admin-{item.id}',
                'title': item.title,
                'message': item.message,
                'type': item.notification_type,
                'isRead': False,
                'createdAt': item.created_at.isoformat(),
                'link': '/teacher/notifications',
            }
            for item in qs
        ]
        return Response(out, status=status.HTTP_200_OK)
