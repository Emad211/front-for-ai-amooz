from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.classes.permissions import IsTeacherUser
from apps.commons.phone_utils import is_valid_iran_mobile, normalize_phone
from apps.classes.models import (
    ClassCreationSession,
    ClassInvitation,
    Enrollment,
    TeacherStudentAccess,
)
from apps.classes.services.invite_codes import get_or_create_invite_code_for_phone
from apps.classes.services.teacher_students import teacher_enrollments


class MultiClassInviteSerializer(serializers.Serializer):
    phones = serializers.ListField(child=serializers.CharField(max_length=32), allow_empty=False)
    sessionIds = serializers.ListField(child=serializers.IntegerField(min_value=1), allow_empty=False)

    def validate_phones(self, values):
        phones = []
        for value in values:
            phone = normalize_phone(value)
            if not is_valid_iran_mobile(phone):
                raise serializers.ValidationError('شماره موبایل معتبر نیست.')
            if phone not in phones:
                phones.append(phone)
        return phones

    def validate_sessionIds(self, values):
        return list(dict.fromkeys(values))


class TeacherStudentInvitationsView(APIView):
    permission_classes = [IsAuthenticated, IsTeacherUser]

    def get(self, request):
        enrolled = Enrollment.objects.filter(
            session_id=OuterRef('session_id'),
            student__phone=OuterRef('phone'),
        )
        invitations = (
            ClassInvitation.objects.filter(
                session__teacher=request.user,
                session__pipeline_type=ClassCreationSession.PipelineType.CLASS,
                session__organization__isnull=True,
            )
            .annotate(has_enrollment=Exists(enrolled))
            .filter(has_enrollment=False)
            .select_related('session')
            .order_by('-created_at')
        )
        return Response([
            {
                'id': invitation.id,
                'phone': invitation.phone,
                'classId': invitation.session_id,
                'classTitle': invitation.session.title,
                'createdAt': invitation.created_at.isoformat(),
            }
            for invitation in invitations
        ])

    def post(self, request):
        serializer = MultiClassInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phones = serializer.validated_data['phones']
        session_ids = serializer.validated_data['sessionIds']
        sessions = list(ClassCreationSession.objects.filter(
            id__in=session_ids,
            teacher=request.user,
            pipeline_type=ClassCreationSession.PipelineType.CLASS,
            organization__isnull=True,
        ))
        if len(sessions) != len(session_ids):
            return Response(
                {'detail': 'یک یا چند کلاس نامعتبر است یا امکان مدیریت دستی دانش‌آموزان آن وجود ندارد.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        created_ids: dict[int, list[int]] = {}
        created_count = 0
        with transaction.atomic():
            for session in sessions:
                for phone in phones:
                    invitation, created = ClassInvitation.objects.get_or_create(
                        session=session,
                        phone=phone,
                        defaults={'invite_code': get_or_create_invite_code_for_phone(phone)},
                    )
                    if created:
                        created_count += 1
                        if session.is_published:
                            created_ids.setdefault(session.id, []).append(invitation.id)
            if created_ids:
                from apps.classes.tasks import send_new_invites_sms_task
                for session_id, invite_ids in created_ids.items():
                    transaction.on_commit(lambda sid=session_id, ids=invite_ids: send_new_invites_sms_task.delay(sid, ids))

        return Response({
            'createdCount': created_count,
            'existingCount': len(session_ids) * len(phones) - created_count,
        }, status=status.HTTP_201_CREATED)


class TeacherStudentInvitationDetailView(APIView):
    permission_classes = [IsAuthenticated, IsTeacherUser]

    def delete(self, request, invitation_id: int):
        invitation = ClassInvitation.objects.filter(
            id=invitation_id,
            session__teacher=request.user,
            session__organization__isnull=True,
        ).first()
        if invitation is None:
            return Response({'detail': 'دعوت پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)
        invitation.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


def _owned_student(teacher, student_id):
    if not teacher_enrollments(teacher=teacher).filter(student_id=student_id).exists():
        return None
    return get_user_model().objects.filter(id=student_id).select_related('studentprofile').first()


class TeacherStudentDetailView(APIView):
    permission_classes = [IsAuthenticated, IsTeacherUser]

    def get(self, request, student_id: int):
        student = _owned_student(request.user, student_id)
        if student is None:
            return Response({'detail': 'دانش‌آموز پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)
        from apps.classes.services.teacher_students import serialize_student_classes
        profile = getattr(student, 'studentprofile', None)
        access = TeacherStudentAccess.objects.filter(teacher=request.user, student=student).first()
        return Response({
            'id': str(student.id),
            'name': student.get_full_name() or student.username or student.phone,
            'email': student.email or '',
            'phone': student.phone or '',
            'grade': profile.get_grade_display() if profile and profile.grade else '',
            'major': profile.get_major_display() if profile and profile.major else '',
            'isSuspended': bool(access and access.is_suspended),
            'classes': serialize_student_classes(teacher=request.user, student=student),
        })


class StudentAccessSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=['active', 'suspended'])
    reason = serializers.CharField(max_length=240, required=False, allow_blank=True)


class TeacherStudentAccessView(APIView):
    permission_classes = [IsAuthenticated, IsTeacherUser]

    def patch(self, request, student_id: int):
        student = _owned_student(request.user, student_id)
        if student is None or not teacher_enrollments(teacher=request.user, organization='personal').filter(student=student).exists():
            return Response({'detail': 'دانش‌آموز پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = StudentAccessSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        suspended = serializer.validated_data['status'] == 'suspended'
        personal_enrollments = teacher_enrollments(
            teacher=request.user, organization='personal',
        ).filter(student=student).select_related('session')
        with transaction.atomic():
            access, _ = TeacherStudentAccess.objects.get_or_create(teacher=request.user, student=student)
            access.is_suspended = suspended
            access.suspended_at = timezone.now() if suspended else None
            access.reason = serializer.validated_data.get('reason', '') if suspended else ''
            access.save(update_fields=['is_suspended', 'suspended_at', 'reason', 'updated_at'])
            session_ids = list(personal_enrollments.values_list('session_id', flat=True))
            if suspended:
                ClassInvitation.objects.filter(session_id__in=session_ids, phone=student.phone).delete()
            else:
                ClassInvitation.objects.bulk_create([
                    ClassInvitation(
                        session=enrollment.session,
                        phone=student.phone,
                        invite_code=get_or_create_invite_code_for_phone(student.phone),
                    )
                    for enrollment in personal_enrollments
                ], ignore_conflicts=True)
        return Response({'status': 'suspended' if suspended else 'active'})


class TeacherStudentRelationshipView(APIView):
    permission_classes = [IsAuthenticated, IsTeacherUser]

    def delete(self, request, student_id: int):
        student = _owned_student(request.user, student_id)
        if student is None:
            return Response({'detail': 'دانش‌آموز پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)
        personal = teacher_enrollments(teacher=request.user, organization='personal').filter(student=student)
        session_ids = list(personal.values_list('session_id', flat=True))
        if not session_ids:
            return Response({'detail': 'دانش‌آموزی در کلاس‌های شخصی شما پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)
        with transaction.atomic():
            personal.delete()
            ClassInvitation.objects.filter(session_id__in=session_ids, phone=student.phone).delete()
            TeacherStudentAccess.objects.filter(teacher=request.user, student=student).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TeacherClassSummaryView(APIView):
    permission_classes = [IsAuthenticated, IsTeacherUser]

    def get(self, request):
        organization = request.query_params.get('organization')
        scope = 'personal' if organization == 'personal' else int(organization) if organization and organization.isdigit() else None
        total = teacher_enrollments(teacher=request.user, organization=scope).values('student_id').distinct().count()
        return Response({'totalStudents': total})
