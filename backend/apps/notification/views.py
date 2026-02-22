from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiResponse

from apps.accounts.models import User
from apps.classes.permissions import IsTeacherUser
from .models import AdminNotification, NotificationReadReceipt
from apps.core.permissions import IsPlatformAdmin as IsAdminUser
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
        user = request.user
        qs = AdminNotification.objects.filter(
            audience__in=[AdminNotification.Audience.ALL, AdminNotification.Audience.TEACHERS],
        ).order_by('-created_at')

        read_ids = set(
            NotificationReadReceipt.objects.filter(user=user).values_list('notification_id', flat=True)
        )

        out = [
            {
                'id': f'admin-{item.id}',
                'title': item.title,
                'message': item.message,
                'type': item.notification_type,
                'isRead': f'admin-{item.id}' in read_ids,
                'createdAt': item.created_at.isoformat(),
                'link': '/teacher/notifications',
            }
            for item in qs
        ]
        return Response(out, status=status.HTTP_200_OK)


class MarkNotificationReadView(APIView):
    """Mark a specific notification as read by the current user."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Notifications'],
        summary='Mark notification as read',
        operation_id='notifications_mark_read',
        request=None,
        responses={200: OpenApiResponse(description="Success")},
    )
    def post(self, request, notification_id):
        NotificationReadReceipt.objects.get_or_create(
            user=request.user,
            notification_id=notification_id
        )
        return Response({'status': 'ok'})


class MarkAllNotificationsReadView(APIView):
    """Mark all currently visible notifications as read for the user."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Notifications'],
        summary='Mark all notifications as read',
        operation_id='notifications_mark_all_read',
        request=None,
        responses={200: OpenApiResponse(description="Success")},
    )
    def post(self, request):
        # Determine notification IDs that should be marked read based on role
        user = request.user
        ids_to_mark = []

        # Admin notifications for everyone
        admin_qs = AdminNotification.objects.filter(
            audience__in=[AdminNotification.Audience.ALL]
        )
        if user.role == User.Role.STUDENT:
            admin_qs = admin_qs | AdminNotification.objects.filter(audience=AdminNotification.Audience.STUDENTS)
        elif user.role == User.Role.TEACHER:
            admin_qs = admin_qs | AdminNotification.objects.filter(audience=AdminNotification.Audience.TEACHERS)
        
        ids_to_mark.extend([f'admin-{item.id}' for item in admin_qs])

        # If student, also handle ClassAnnouncements
        if user.role == User.Role.STUDENT:
            from apps.classes.models import ClassAnnouncement, ClassCreationSession
            phone = (getattr(user, 'phone', None) or '').strip()
            if phone:
                announcements = ClassAnnouncement.objects.filter(
                    session__invites__phone=phone
                ).distinct()
                ids_to_mark.extend([f'announcement-{a.id}' for a in announcements])

        # Bulk create receipts
        receipts = [
            NotificationReadReceipt(user=user, notification_id=nid)
            for nid in ids_to_mark
        ]
        NotificationReadReceipt.objects.bulk_create(receipts, ignore_conflicts=True)

        return Response({'status': 'ok'})
