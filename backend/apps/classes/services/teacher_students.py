from django.db.models import Avg, Count, Max, Min

from apps.classes.models import (
    ClassCreationSession, ClassFinalExam, ClassSectionQuiz, ClassUnit,
    Enrollment, StudentUnitProgress, TeacherStudentAccess,
)
from apps.classes.services.progress import activity_status, session_roster_stats, teacher_roster_stats, units_per_session


def teacher_enrollments(*, teacher, organization=None):
    qs = Enrollment.objects.filter(
        session__teacher=teacher,
        session__pipeline_type=ClassCreationSession.PipelineType.CLASS,
    )
    if organization == 'personal':
        qs = qs.filter(session__organization__isnull=True)
    elif organization is not None:
        qs = qs.filter(session__organization_id=organization)
    return qs


def serialize_teacher_students(*, teacher) -> list[dict]:
    rows = list(
        teacher_enrollments(teacher=teacher)
        .values(
            'student_id', 'student__first_name', 'student__last_name',
            'student__username', 'student__email', 'student__phone',
        )
        .annotate(
            enrolled_classes=Count('session_id', distinct=True),
            join_date=Min('joined_at'),
            last_activity=Max('last_activity_at'),
        )
        .order_by('student_id')
    )
    user_ids = [row['student_id'] for row in rows]
    stats = teacher_roster_stats(teacher=teacher, user_ids=user_ids)
    units = units_per_session(teacher=teacher)
    sessions_by_student: dict[int, set[int]] = {}
    for row in teacher_enrollments(teacher=teacher).values('student_id', 'session_id'):
        sessions_by_student.setdefault(row['student_id'], set()).add(row['session_id'])
    suspended = set(
        TeacherStudentAccess.objects.filter(
            teacher=teacher, student_id__in=user_ids, is_suspended=True,
        ).values_list('student_id', flat=True)
    )
    organization_students = set(
        teacher_enrollments(teacher=teacher)
        .filter(session__organization__isnull=False)
        .values_list('student_id', flat=True)
    )
    suspended -= organization_students

    output: list[dict] = []
    for row in rows:
        student_id = row['student_id']
        first = (row['student__first_name'] or '').strip()
        last = (row['student__last_name'] or '').strip()
        phone = (row['student__phone'] or '').strip()
        student_stats = stats.get(student_id) or {}
        average = student_stats.get('averageScore')
        score = int(average or 0)
        total_lessons = sum(units.get(sid, 0) for sid in sessions_by_student.get(student_id, set()))
        completed = min(int(student_stats.get('completedLessons') or 0), total_lessons) if total_lessons else 0
        last_activity = student_stats.get('lastActivity') or row['last_activity']
        join_date = row['join_date']
        output.append({
            'id': str(student_id),
            'name': f'{first} {last}'.strip() or (row['student__username'] or '').strip() or phone,
            'email': (row['student__email'] or '').strip(),
            'phone': phone,
            'inviteCode': '',
            'avatar': '',
            'enrolledClasses': int(row['enrolled_classes'] or 0),
            'completedLessons': completed,
            'totalLessons': total_lessons,
            'averageScore': score,
            'status': 'suspended' if student_id in suspended else activity_status(last_activity),
            'joinDate': join_date.isoformat() if join_date else '',
            'lastActivity': last_activity.isoformat() if last_activity else (join_date.isoformat() if join_date else ''),
            'performance': 'excellent' if average is not None and score >= 85 else 'good' if average is not None and score >= 70 else 'needs-improvement',
        })
    return output


def serialize_session_students(*, session) -> list[dict]:
    enrollments = list(
        Enrollment.objects.filter(session=session)
        .select_related('student')
        .order_by('-joined_at')
    )
    student_ids = [item.student_id for item in enrollments]
    stats = session_roster_stats(session=session, user_ids=student_ids)
    output = []
    for enrollment in enrollments:
        student = enrollment.student
        row = stats.get(student.id) or {}
        output.append({
            'id': str(student.id),
            'name': student.get_full_name() or student.username or student.phone,
            'email': student.email or '',
            'phone': student.phone or '',
            'inviteCode': '',
            'avatar': '',
            'progress': int(row.get('progress') or 0),
            'completedLessons': int(row.get('completedLessons') or 0),
            'totalLessons': int(row.get('totalLessons') or 0),
            'averageScore': int(row.get('averageScore') or 0),
            'status': activity_status(enrollment.last_activity_at),
            'joinDate': enrollment.joined_at.date().isoformat(),
            'lastActivity': (enrollment.last_activity_at or enrollment.joined_at).isoformat(),
        })
    return output


def serialize_student_classes(*, teacher, student) -> list[dict]:
    enrollments = list(
        teacher_enrollments(teacher=teacher).filter(student=student)
        .select_related('session').order_by('-joined_at')
    )
    session_ids = [item.session_id for item in enrollments]
    totals = {
        row['session_id']: row['count']
        for row in ClassUnit.objects.filter(session_id__in=session_ids)
        .values('session_id').annotate(count=Count('id'))
    }
    completed = {
        row['session_id']: row['count']
        for row in StudentUnitProgress.objects.filter(student=student, session_id__in=session_ids)
        .values('session_id').annotate(count=Count('id'))
    }
    quizzes = {
        row['session_id']: (row['average'], row['count'])
        for row in ClassSectionQuiz.objects.filter(
            student=student, session_id__in=session_ids, last_score_0_100__isnull=False,
        ).values('session_id').annotate(average=Avg('last_score_0_100'), count=Count('id'))
    }
    finals = {
        row['session_id']: (row['average'], row['count'])
        for row in ClassFinalExam.objects.filter(
            student=student, session_id__in=session_ids, last_score_0_100__isnull=False,
        ).values('session_id').annotate(average=Avg('last_score_0_100'), count=Count('id'))
    }
    output = []
    for enrollment in enrollments:
        session_id = enrollment.session_id
        total = totals.get(session_id, 0)
        done = min(completed.get(session_id, 0), total) if total else 0
        qa, qn = quizzes.get(session_id, (0, 0))
        fa, fn = finals.get(session_id, (0, 0))
        score_count = qn + fn
        score = int(round(((qa or 0) * qn + (fa or 0) * fn) / score_count)) if score_count else 0
        output.append({
            'id': session_id,
            'title': enrollment.session.title,
            'progress': int(round(done / total * 100)) if total else 0,
            'averageScore': score,
            'lastActivity': enrollment.last_activity_at.isoformat() if enrollment.last_activity_at else None,
            'isOrganizationClass': enrollment.session.organization_id is not None,
        })
    return output
