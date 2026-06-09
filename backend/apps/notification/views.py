from __future__ import annotations

import re

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiResponse

from django.db import transaction

from apps.accounts.models import User
from apps.classes.permissions import IsTeacherUser
from .models import (
    AdminNotification,
    NotificationReadReceipt,
    TeacherNotification,
    TeacherNotificationRecipient,
    UserNotificationPreference,
)
from apps.core.permissions import IsPlatformAdmin as IsAdminUser
from .serializers import (
    AdminNotificationCreateSerializer,
    AdminNotificationSerializer,
    NotificationPreferenceSerializer,
    TeacherBroadcastCreateSerializer,
    TeacherBroadcastResultSerializer,
    TeacherMessageRecipientSerializer,
    UserRecipientSerializer,
)
from .services import teacher_student_phones, teacher_student_recipients


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


class TeacherMessageRecipientsView(APIView):
    """List the teacher's own students for the message recipient picker."""

    permission_classes = [IsAuthenticated, IsTeacherUser]

    @extend_schema(
        tags=['Notifications'],
        summary='List the teacher\'s students (message recipients)',
        operation_id='teacher_message_recipients',
        responses={200: TeacherMessageRecipientSerializer(many=True)},
    )
    def get(self, request):
        recipients = teacher_student_recipients(teacher=request.user)
        return Response(TeacherMessageRecipientSerializer(recipients, many=True).data)


class TeacherNotificationBroadcastView(APIView):
    """Send a message from a teacher to their own students.

    Delivered in-app (student notification feed) and, optionally, by SMS. A
    teacher can only target phones that belong to their own students.
    """

    permission_classes = [IsAuthenticated, IsTeacherUser]

    @extend_schema(
        tags=['Notifications'],
        summary='Send a teacher broadcast message to students',
        operation_id='teacher_notifications_broadcast',
        request=TeacherBroadcastCreateSerializer,
        responses={201: TeacherBroadcastResultSerializer},
    )
    def post(self, request):
        serializer = TeacherBroadcastCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        own_students = teacher_student_phones(teacher=request.user)
        if not own_students:
            return Response(
                {'detail': 'هنوز دانش‌آموزی برای ارسال پیام ندارید.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if data.get('sendToAll'):
            target_phones = set(own_students)
        else:
            requested = {(p or '').strip() for p in data.get('recipientPhones') or []}
            # Security: silently drop anyone who is not this teacher's student.
            target_phones = requested & own_students

        if not target_phones:
            return Response(
                {'detail': 'گیرنده‌ای انتخاب نشده است.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        send_sms = bool(data.get('sendSms'))

        with transaction.atomic():
            notif = TeacherNotification.objects.create(
                teacher=request.user,
                title=data['title'],
                message=data['message'],
                notification_type=data.get(
                    'notification_type', AdminNotification.NotificationType.MESSAGE
                ),
                sms_sent=send_sms,
            )
            TeacherNotificationRecipient.objects.bulk_create(
                [
                    TeacherNotificationRecipient(notification=notif, phone=phone)
                    for phone in sorted(target_phones)
                ],
                ignore_conflicts=True,
            )

        if send_sms:
            from apps.classes.tasks import send_teacher_message_sms_task

            notif_id = notif.id

            def _dispatch_sms(nid=notif_id):
                send_teacher_message_sms_task.delay(nid)

            transaction.on_commit(_dispatch_sms)

        payload = {
            'id': notif.id,
            'title': notif.title,
            'message': notif.message,
            'type': notif.notification_type,
            'recipientCount': len(target_phones),
            'smsQueued': send_sms,
            'createdAt': notif.created_at.isoformat(),
        }
        return Response(
            TeacherBroadcastResultSerializer(payload).data, status=status.HTTP_201_CREATED
        )


class NotificationPreferencesView(APIView):
    """Per-user notification channel preferences (GET/PATCH). Role-agnostic."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Notifications'],
        summary='Get notification preferences',
        operation_id='notification_preferences_get',
        responses={200: NotificationPreferenceSerializer},
    )
    def get(self, request):
        prefs, _ = UserNotificationPreference.objects.get_or_create(user=request.user)
        return Response(NotificationPreferenceSerializer(prefs).data)

    @extend_schema(
        tags=['Notifications'],
        summary='Update notification preferences',
        operation_id='notification_preferences_update',
        request=NotificationPreferenceSerializer,
        responses={200: NotificationPreferenceSerializer},
    )
    def patch(self, request):
        prefs, _ = UserNotificationPreference.objects.get_or_create(user=request.user)
        serializer = NotificationPreferenceSerializer(prefs, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(NotificationPreferenceSerializer(prefs).data)


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
        # Guard the id format so a client can't spam arbitrary strings and create
        # unbounded read-receipt rows. Real ids are "<source>-<pk>"
        # (admin-/teacher-/announcement-/system-…).
        nid = str(notification_id)
        if len(nid) > 64 or not re.match(r'^[a-z_]+-\d+$', nid):
            return Response({'detail': 'شناسه اعلان نامعتبر است.'}, status=status.HTTP_400_BAD_REQUEST)
        NotificationReadReceipt.objects.get_or_create(
            user=request.user,
            notification_id=nid,
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
        
        # values_list -> fetch only the id column instead of materializing full
        # model instances (esp. ClassAnnouncement, which carries large text bodies)
        # just to read .id. Same "mark ALL" semantics — no cap, no behavior change.
        ids_to_mark.extend([f'admin-{i}' for i in admin_qs.values_list('id', flat=True)])

        # If student, also handle ClassAnnouncements + teacher messages addressed to them.
        if user.role == User.Role.STUDENT:
            from apps.classes.models import ClassAnnouncement
            phone = (getattr(user, 'phone', None) or '').strip()
            if phone:
                announcement_ids = (
                    ClassAnnouncement.objects.filter(session__invites__phone=phone)
                    .values_list('id', flat=True)
                    .distinct()
                )
                ids_to_mark.extend([f'announcement-{aid}' for aid in announcement_ids])

                teacher_notif_ids = (
                    TeacherNotification.objects.filter(recipients__phone=phone)
                    .values_list('id', flat=True)
                    .distinct()
                )
                ids_to_mark.extend([f'teacher-{nid}' for nid in teacher_notif_ids])

        # Bulk create receipts
        receipts = [
            NotificationReadReceipt(user=user, notification_id=nid)
            for nid in ids_to_mark
        ]
        NotificationReadReceipt.objects.bulk_create(receipts, ignore_conflicts=True)

        return Response({'status': 'ok'})
