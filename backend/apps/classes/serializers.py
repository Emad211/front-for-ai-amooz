import json

from django.conf import settings
from django.utils.dateparse import parse_datetime
from rest_framework import serializers

from drf_spectacular.utils import extend_schema_field

from apps.commons.phone_utils import is_valid_iran_mobile, normalize_phone

from .models import ClassAnnouncement, ClassCreationSession, ClassInvitation, ClassPrerequisite
from .services.exercise_workflow import (
    ANSWER_LAYOUT_CHOICES,
    SOURCE_ROLE_CHOICES,
    WRITING_MODE_CHOICES,
)
from .services.session_workflow import serialize_session_workflow_fields


def is_pdf_upload(value) -> bool:
    """True when an uploaded file is a PDF (by MIME or .pdf extension)."""
    content_type = (getattr(value, 'content_type', '') or '').lower()
    name = str(getattr(value, 'name', '') or '').lower()
    return content_type == 'application/pdf' or name.endswith('.pdf')


def validate_step1_upload(value):
    """Shared validation for Step 1 uploads: audio, video, or PDF.

    PDFs use the (smaller) PDF size cap; media uses the transcription cap.
    """
    content_type = (getattr(value, 'content_type', '') or '').lower()
    is_media = content_type.startswith('audio/') or content_type.startswith('video/')
    is_pdf = is_pdf_upload(value)
    if not (is_media or is_pdf):
        raise serializers.ValidationError(
            'Only audio, video, or PDF uploads are supported.'
        )

    if is_pdf:
        max_bytes = getattr(settings, 'PDF_MAX_UPLOAD_BYTES', 100 * 1024 * 1024)
    else:
        max_bytes = getattr(settings, 'TRANSCRIPTION_MAX_UPLOAD_BYTES', 500 * 1024 * 1024)
    max_mb = max_bytes // (1024 * 1024)
    if getattr(value, 'size', 0) > max_bytes:
        raise serializers.ValidationError(f'File is too large (max {max_mb}MB).')

    return value


class Step1TranscribeRequestSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True)
    file = serializers.FileField()
    client_request_id = serializers.UUIDField(required=False)
    run_full_pipeline = serializers.BooleanField(required=False, default=False)
    pending_exercises = serializers.CharField(required=False, allow_blank=True, default='[]')

    def validate_file(self, value):
        return validate_step1_upload(value)

    def validate_pending_exercises(self, value):
        raw = value
        if isinstance(raw, str):
            try:
                raw = json.loads(raw or '[]')
            except json.JSONDecodeError as exc:
                raise serializers.ValidationError('تنظیمات تمرین‌های همراه نامعتبر است.') from exc
        if not isinstance(raw, list):
            raise serializers.ValidationError('تنظیمات تمرین‌های همراه نامعتبر است.')
        out: list[dict] = []
        seen_exercise_keys: set[str] = set()
        for ex_idx, item in enumerate(raw, start=1):
            if not isinstance(item, dict):
                raise serializers.ValidationError(f'تمرین شمارهٔ {ex_idx} نامعتبر است.')
            client_exercise_key = str(item.get('clientExerciseKey') or '').strip()
            if not client_exercise_key:
                raise serializers.ValidationError(f'کلید تمرین شمارهٔ {ex_idx} خالی است.')
            if client_exercise_key in seen_exercise_keys:
                raise serializers.ValidationError(f'کلید تمرین شمارهٔ {ex_idx} تکراری است.')
            seen_exercise_keys.add(client_exercise_key)
            title = str(item.get('title') or '').strip()
            if not title:
                raise serializers.ValidationError(f'عنوان تمرین شمارهٔ {ex_idx} الزامی است.')
            no_deadline = bool(item.get('noDeadline', item.get('no_deadline', False)))
            deadline = item.get('deadline')
            if not no_deadline and not deadline:
                raise serializers.ValidationError(f'مهلت تمرین شمارهٔ {ex_idx} مشخص نشده است.')
            allow_late = bool(item.get('allowLate', item.get('allow_late', False)))
            if no_deadline and allow_late:
                raise serializers.ValidationError(
                    f'ارسال دیرهنگام برای تمرین بدون مهلت شمارهٔ {ex_idx} قابل فعال‌سازی نیست.'
                )
            normalized_deadline = None
            if deadline:
                normalized_deadline = parse_datetime(str(deadline))
                if normalized_deadline is None:
                    raise serializers.ValidationError(f'مهلت تمرین شمارهٔ {ex_idx} نامعتبر است.')
            sources = item.get('sources')
            if not isinstance(sources, list) or not sources:
                raise serializers.ValidationError(f'حداقل یک منبع برای تمرین شمارهٔ {ex_idx} لازم است.')
            seen_keys: set[str] = set()
            norm_sources: list[dict] = []
            for src_idx, src in enumerate(sources, start=1):
                if not isinstance(src, dict):
                    raise serializers.ValidationError(f'منبع شمارهٔ {src_idx} در تمرین {ex_idx} نامعتبر است.')
                client_file_key = str(src.get('clientFileKey') or '').strip()
                if not client_file_key:
                    raise serializers.ValidationError(f'کلید فایل منبع {src_idx} در تمرین {ex_idx} خالی است.')
                if client_file_key in seen_keys:
                    raise serializers.ValidationError(f'کلید فایل منبع {src_idx} در تمرین {ex_idx} تکراری است.')
                seen_keys.add(client_file_key)
                role = str(src.get('role') or 'auto')
                writing_mode = str(src.get('writingMode') or 'auto')
                answer_layout = str(src.get('answerLayout') or 'auto')
                if role not in SOURCE_ROLE_CHOICES:
                    raise serializers.ValidationError(f'نقش منبع {src_idx} در تمرین {ex_idx} نامعتبر است.')
                if writing_mode not in WRITING_MODE_CHOICES:
                    raise serializers.ValidationError(f'نوع نوشتار منبع {src_idx} در تمرین {ex_idx} نامعتبر است.')
                if answer_layout not in ANSWER_LAYOUT_CHOICES:
                    raise serializers.ValidationError(f'چیدمان پاسخ منبع {src_idx} در تمرین {ex_idx} نامعتبر است.')
                norm_sources.append({
                    'clientFileKey': client_file_key,
                    'role': role,
                    'writingMode': writing_mode,
                    'answerLayout': answer_layout,
                })
            out.append({
                'clientExerciseKey': client_exercise_key,
                'title': title,
                'noDeadline': no_deadline,
                'deadline': normalized_deadline.isoformat() if normalized_deadline else None,
                'allowLate': allow_late,
                'assistantEnabled': bool(item.get('assistantEnabled', item.get('assistant_enabled', True))),
                'teacherNote': str(item.get('teacherNote', item.get('teacher_note', '')) or '').strip(),
                'sources': norm_sources,
            })
        return out


class Step1TranscribeResponseSerializer(serializers.ModelSerializer):
    workflowStage = serializers.SerializerMethodField()
    workflowMessage = serializers.SerializerMethodField()
    progressPercent = serializers.SerializerMethodField()
    workflowWarnings = serializers.SerializerMethodField()
    readyForReview = serializers.SerializerMethodField()
    reviewReadyNotifiedAt = serializers.SerializerMethodField()
    pendingExercises = serializers.SerializerMethodField()

    def _wf(self, obj):
        return serialize_session_workflow_fields(obj)

    def get_workflowStage(self, obj):
        return self._wf(obj)['workflowStage']

    def get_workflowMessage(self, obj):
        return self._wf(obj)['workflowMessage']

    def get_progressPercent(self, obj):
        return self._wf(obj)['progressPercent']

    def get_workflowWarnings(self, obj):
        return self._wf(obj)['workflowWarnings']

    def get_readyForReview(self, obj):
        return self._wf(obj)['readyForReview']

    def get_reviewReadyNotifiedAt(self, obj):
        return self._wf(obj)['reviewReadyNotifiedAt']

    def get_pendingExercises(self, obj):
        return self._wf(obj)['pendingExercises']

    class Meta:
        model = ClassCreationSession
        fields = [
            'id',
            'status',
            'title',
            'description',
            'source_type',
            'source_page_count',
            'source_mime_type',
            'source_original_name',
            'transcript_markdown',
            'created_at',
            'workflowStage',
            'workflowMessage',
            'progressPercent',
            'workflowWarnings',
            'readyForReview',
            'reviewReadyNotifiedAt',
            'pendingExercises',
        ]


class Step2StructureRequestSerializer(serializers.Serializer):
    session_id = serializers.IntegerField(min_value=1)


class Step2StructureResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClassCreationSession
        fields = [
            'id',
            'status',
            'title',
            'description',
            'structure_json',
            'created_at',
        ]


class Step3PrerequisitesRequestSerializer(serializers.Serializer):
    session_id = serializers.IntegerField(min_value=1)


class PrerequisiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClassPrerequisite
        fields = ['id', 'order', 'name', 'teaching_text']


class Step3PrerequisitesResponseSerializer(serializers.ModelSerializer):
    prerequisites = serializers.SerializerMethodField()

    @extend_schema_field(PrerequisiteSerializer(many=True))
    def get_prerequisites(self, obj: ClassCreationSession):
        qs = obj.prerequisites.order_by('order')
        return PrerequisiteSerializer(qs, many=True).data

    class Meta:
        model = ClassCreationSession
        fields = ['id', 'status', 'title', 'description', 'created_at', 'prerequisites']


class Step4PrerequisiteTeachingRequestSerializer(serializers.Serializer):
    session_id = serializers.IntegerField(min_value=1)
    prerequisite_name = serializers.CharField(max_length=255, required=False, allow_blank=True)


class Step4PrerequisiteTeachingResponseSerializer(serializers.ModelSerializer):
    prerequisites = serializers.SerializerMethodField()

    @extend_schema_field(PrerequisiteSerializer(many=True))
    def get_prerequisites(self, obj: ClassCreationSession):
        qs = obj.prerequisites.order_by('order')
        return PrerequisiteSerializer(qs, many=True).data

    class Meta:
        model = ClassCreationSession
        fields = ['id', 'status', 'title', 'description', 'created_at', 'prerequisites']


class Step5RecapRequestSerializer(serializers.Serializer):
    session_id = serializers.IntegerField(min_value=1)


class Step5RecapResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClassCreationSession
        fields = ['id', 'status', 'title', 'description', 'created_at', 'recap_markdown']


class ClassCreationSessionListSerializer(serializers.ModelSerializer):
    invites_count = serializers.IntegerField(read_only=True, source='_invites_count')
    lessons_count = serializers.IntegerField(read_only=True, source='_lessons_count')
    organization_id = serializers.IntegerField(read_only=True, allow_null=True)
    workflowStage = serializers.SerializerMethodField()
    workflowMessage = serializers.SerializerMethodField()
    progressPercent = serializers.SerializerMethodField()
    workflowWarnings = serializers.SerializerMethodField()
    readyForReview = serializers.SerializerMethodField()
    reviewReadyNotifiedAt = serializers.SerializerMethodField()
    pendingExercises = serializers.SerializerMethodField()

    def _wf(self, obj):
        return serialize_session_workflow_fields(obj)

    def get_workflowStage(self, obj):
        return self._wf(obj)['workflowStage']

    def get_workflowMessage(self, obj):
        return self._wf(obj)['workflowMessage']

    def get_progressPercent(self, obj):
        return self._wf(obj)['progressPercent']

    def get_workflowWarnings(self, obj):
        return self._wf(obj)['workflowWarnings']

    def get_readyForReview(self, obj):
        return self._wf(obj)['readyForReview']

    def get_reviewReadyNotifiedAt(self, obj):
        return self._wf(obj)['reviewReadyNotifiedAt']

    def get_pendingExercises(self, obj):
        return self._wf(obj)['pendingExercises']

    class Meta:
        model = ClassCreationSession
        fields = [
            'id',
            'status',
            'title',
            'description',
            'source_type',
            'is_published',
            'published_at',
            'invites_count',
            'lessons_count',
            'organization_id',
            'created_at',
            'updated_at',
            'workflowStage',
            'workflowMessage',
            'progressPercent',
            'workflowWarnings',
            'readyForReview',
            'reviewReadyNotifiedAt',
            'pendingExercises',
        ]


class ClassCreationSessionDetailSerializer(serializers.ModelSerializer):
    invites_count = serializers.SerializerMethodField()
    workflowStage = serializers.SerializerMethodField()
    workflowMessage = serializers.SerializerMethodField()
    progressPercent = serializers.SerializerMethodField()
    workflowWarnings = serializers.SerializerMethodField()
    readyForReview = serializers.SerializerMethodField()
    reviewReadyNotifiedAt = serializers.SerializerMethodField()
    pendingExercises = serializers.SerializerMethodField()

    def get_invites_count(self, obj: ClassCreationSession) -> int:
        # Prefer the annotation if available (from list views), otherwise fall back.
        if hasattr(obj, '_invites_count'):
            return obj._invites_count
        teacher_phone = (getattr(obj.teacher, 'phone', '') or '').strip()
        invites = obj.invites.exclude(phone=teacher_phone) if teacher_phone else obj.invites
        return invites.values('phone').distinct().count()

    def _wf(self, obj):
        return serialize_session_workflow_fields(obj)

    def get_workflowStage(self, obj):
        return self._wf(obj)['workflowStage']

    def get_workflowMessage(self, obj):
        return self._wf(obj)['workflowMessage']

    def get_progressPercent(self, obj):
        return self._wf(obj)['progressPercent']

    def get_workflowWarnings(self, obj):
        return self._wf(obj)['workflowWarnings']

    def get_readyForReview(self, obj):
        return self._wf(obj)['readyForReview']

    def get_reviewReadyNotifiedAt(self, obj):
        return self._wf(obj)['reviewReadyNotifiedAt']

    def get_pendingExercises(self, obj):
        return self._wf(obj)['pendingExercises']

    class Meta:
        model = ClassCreationSession
        fields = [
            'id',
            'status',
            'title',
            'description',
            'level',
            'duration',
            'source_type',
            'source_page_count',
            'source_mime_type',
            'source_original_name',
            'transcript_markdown',
            'structure_json',
            'recap_markdown',
            'error_detail',
            'is_published',
            'published_at',
            'invites_count',
            'created_at',
            'updated_at',
            'workflowStage',
            'workflowMessage',
            'progressPercent',
            'workflowWarnings',
            'readyForReview',
            'reviewReadyNotifiedAt',
            'pendingExercises',
        ]

class ClassAnnouncementSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClassAnnouncement
        fields = ['id', 'title', 'content', 'priority', 'created_at', 'updated_at']

class ClassAnnouncementCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    content = serializers.CharField()
    priority = serializers.ChoiceField(choices=ClassAnnouncement.Priority.choices, default=ClassAnnouncement.Priority.MEDIUM)

class ClassAnnouncementUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255, required=False)
    content = serializers.CharField(required=False)
    priority = serializers.ChoiceField(choices=ClassAnnouncement.Priority.choices, required=False)


class ClassCreationSessionUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    level = serializers.CharField(required=False, allow_blank=True, max_length=64)
    duration = serializers.CharField(required=False, allow_blank=True, max_length=64)
    structure_json = serializers.JSONField(required=False)

    def validate_structure_json(self, value):
        # Allow either:
        # - object/array (preferred)
        # - string containing valid JSON
        if isinstance(value, str):
            s = value.strip()
            if not s:
                return ''
            try:
                json.loads(s)
            except Exception:
                raise serializers.ValidationError('Invalid JSON string.')
            return s

        try:
            return json.dumps(value, ensure_ascii=False)
        except Exception:
            raise serializers.ValidationError('Invalid JSON payload.')


class ClassInvitationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClassInvitation
        fields = ['id', 'phone', 'invite_code', 'created_at']


class ClassInvitationCreateSerializer(serializers.Serializer):
    phones = serializers.ListField(
        child=serializers.CharField(max_length=32),
        allow_empty=False,
    )

    def validate_phones(self, value):
        out: list[str] = []
        for raw in value:
            digits = normalize_phone(raw)
            if not is_valid_iran_mobile(digits):
                raise serializers.ValidationError('Invalid phone number.')
            out.append(digits)
        # De-dupe while preserving order
        seen = set()
        unique: list[str] = []
        for p in out:
            if p in seen:
                continue
            seen.add(p)
            unique.append(p)
        return unique


class TeacherStudentSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    email = serializers.CharField()
    phone = serializers.CharField()
    inviteCode = serializers.CharField()
    avatar = serializers.CharField()
    enrolledClasses = serializers.IntegerField(min_value=0)
    completedLessons = serializers.IntegerField(min_value=0)
    totalLessons = serializers.IntegerField(min_value=0)
    averageScore = serializers.IntegerField(min_value=0)
    status = serializers.CharField()
    joinDate = serializers.CharField()
    lastActivity = serializers.CharField()
    performance = serializers.CharField()


class ClassSessionStudentSerializer(serializers.Serializer):
    """Real per-student roster for a single class session (replaces invite stubs)."""

    id = serializers.CharField()
    name = serializers.CharField()
    email = serializers.CharField(allow_blank=True)
    phone = serializers.CharField(allow_blank=True)
    inviteCode = serializers.CharField(allow_blank=True)
    avatar = serializers.CharField(allow_blank=True)
    progress = serializers.IntegerField(min_value=0)
    completedLessons = serializers.IntegerField(min_value=0)
    totalLessons = serializers.IntegerField(min_value=0)
    averageScore = serializers.IntegerField(min_value=0)
    status = serializers.CharField()
    joinDate = serializers.CharField()
    lastActivity = serializers.CharField()


class TeacherAnalyticsStatSerializer(serializers.Serializer):
    title = serializers.CharField()
    value = serializers.CharField()
    change = serializers.CharField()
    trend = serializers.CharField()
    icon = serializers.CharField()


class TeacherAnalyticsChartPointSerializer(serializers.Serializer):
    name = serializers.CharField()
    students = serializers.IntegerField()


class TeacherAnalyticsDistributionItemSerializer(serializers.Serializer):
    name = serializers.CharField()
    value = serializers.IntegerField()


class TeacherAnalyticsActivitySerializer(serializers.Serializer):
    id = serializers.CharField()
    type = serializers.CharField()
    user = serializers.CharField()
    action = serializers.CharField()
    time = serializers.CharField()
    icon = serializers.CharField()
    color = serializers.CharField()
    bg = serializers.CharField()


class StudentCourseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    description = serializers.CharField(allow_blank=True)
    tags = serializers.ListField(child=serializers.CharField(), allow_empty=True)

    instructor = serializers.CharField(required=False, allow_blank=True)
    progress = serializers.IntegerField(required=False)
    studentsCount = serializers.IntegerField(required=False)
    lessonsCount = serializers.IntegerField(required=False)
    status = serializers.CharField(required=False)
    createdAt = serializers.CharField(required=False, allow_blank=True)
    lastActivity = serializers.CharField(required=False, allow_blank=True)
    sourceType = serializers.CharField(required=False, allow_blank=True)


class StudentLessonSerializer(serializers.Serializer):
    id = serializers.CharField()
    title = serializers.CharField()
    type = serializers.CharField(required=False, allow_blank=True)
    isActive = serializers.BooleanField(required=False)
    isCompleted = serializers.BooleanField(required=False)
    isLocked = serializers.BooleanField(required=False)
    isSpecial = serializers.BooleanField(required=False)
    content = serializers.CharField(required=False, allow_blank=True)


class StudentChapterSerializer(serializers.Serializer):
    id = serializers.CharField()
    title = serializers.CharField()
    lessons = StudentLessonSerializer(many=True)


class StudentCourseContentSerializer(serializers.Serializer):
    id = serializers.CharField()
    title = serializers.CharField()
    description = serializers.CharField(allow_blank=True)
    progress = serializers.IntegerField()
    level = serializers.CharField()
    duration = serializers.CharField()
    recapMarkdown = serializers.CharField(required=False, allow_blank=True)
    learningObjectives = serializers.ListField(child=serializers.CharField(), required=False, allow_empty=True)
    prerequisites = PrerequisiteSerializer(many=True, required=False)
    chapters = StudentChapterSerializer(many=True)


class StudentChapterQuizQuestionSerializer(serializers.Serializer):
    id = serializers.CharField()
    type = serializers.CharField()
    question = serializers.CharField()
    options = serializers.ListField(child=serializers.CharField(), required=False, allow_empty=True)
    difficulty = serializers.CharField(required=False, allow_blank=True)


class StudentNotificationSerializer(serializers.Serializer):
    id = serializers.CharField()
    title = serializers.CharField()
    message = serializers.CharField()
    type = serializers.CharField()
    isRead = serializers.BooleanField()
    createdAt = serializers.CharField()
    link = serializers.CharField(required=False, allow_blank=True)


class StudentChapterQuizResponseSerializer(serializers.Serializer):
    quiz_id = serializers.IntegerField()
    session_id = serializers.IntegerField()
    chapter_id = serializers.CharField()
    chapter_title = serializers.CharField()
    passing_score = serializers.IntegerField()
    questions = StudentChapterQuizQuestionSerializer(many=True)
    last_score_0_100 = serializers.IntegerField(required=False, allow_null=True)
    last_passed = serializers.BooleanField(required=False, allow_null=True)


class StudentChapterQuizSubmitRequestSerializer(serializers.Serializer):
    answers = serializers.DictField(child=serializers.CharField(allow_blank=True), allow_empty=False)


class StudentChapterQuizSubmitResponseSerializer(serializers.Serializer):
    score_0_100 = serializers.IntegerField()
    passed = serializers.BooleanField()
    passing_score = serializers.IntegerField()
    per_question = serializers.ListField(child=serializers.DictField(), allow_empty=True)
    course_progress = serializers.IntegerField(required=False)


class StudentFinalExamQuestionSerializer(serializers.Serializer):
    id = serializers.CharField()
    type = serializers.CharField()
    question = serializers.CharField()
    options = serializers.ListField(child=serializers.CharField(), required=False, allow_empty=True)
    points = serializers.IntegerField(required=False)
    chapter = serializers.CharField(required=False, allow_blank=True)


class StudentFinalExamResponseSerializer(serializers.Serializer):
    exam_id = serializers.IntegerField()
    session_id = serializers.IntegerField()
    exam_title = serializers.CharField()
    time_limit = serializers.IntegerField()
    passing_score = serializers.IntegerField()
    questions = StudentFinalExamQuestionSerializer(many=True)
    last_score_0_100 = serializers.IntegerField(required=False, allow_null=True)
    last_passed = serializers.BooleanField(required=False, allow_null=True)


class StudentFinalExamSubmitRequestSerializer(serializers.Serializer):
    answers = serializers.DictField(child=serializers.CharField(allow_blank=True), allow_empty=False)


class StudentFinalExamSubmitResponseSerializer(serializers.Serializer):
    score_0_100 = serializers.IntegerField()
    passed = serializers.BooleanField()
    passing_score = serializers.IntegerField()
    per_question = serializers.ListField(child=serializers.DictField(), allow_empty=True)
    course_progress = serializers.IntegerField(required=False)


class InviteCodeVerifySerializer(serializers.Serializer):
    code = serializers.CharField(max_length=64)

    def validate_code(self, value: str) -> str:
        s = (value or '').strip()
        if not s:
            raise serializers.ValidationError('کد دعوت الزامی است.')
        return s


class InviteCodeVerifyResponseSerializer(serializers.Serializer):
    valid = serializers.BooleanField()
    session_id = serializers.IntegerField(required=False)
    title = serializers.CharField(required=False, allow_blank=True)


# ==========================================================================
# EXAM PREP PIPELINE SERIALIZERS
# ==========================================================================


class ExamPrepStep1TranscribeRequestSerializer(serializers.Serializer):
    """Request serializer for Exam Prep Step 1: Transcription."""
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True)
    file = serializers.FileField()
    client_request_id = serializers.UUIDField(required=False)
    run_full_pipeline = serializers.BooleanField(required=False, default=False)
    pending_exercises = serializers.CharField(required=False, allow_blank=True, default='[]')

    def validate_file(self, value):
        return validate_step1_upload(value)

    def validate_pending_exercises(self, value):
        return []


class ExamPrepStep1TranscribeResponseSerializer(serializers.ModelSerializer):
    """Response serializer for Exam Prep Step 1: Transcription."""
    workflowStage = serializers.SerializerMethodField()
    workflowMessage = serializers.SerializerMethodField()
    progressPercent = serializers.SerializerMethodField()
    workflowWarnings = serializers.SerializerMethodField()
    readyForReview = serializers.SerializerMethodField()
    reviewReadyNotifiedAt = serializers.SerializerMethodField()
    pendingExercises = serializers.SerializerMethodField()

    def _wf(self, obj):
        return serialize_session_workflow_fields(obj)

    def get_workflowStage(self, obj):
        return self._wf(obj)['workflowStage']

    def get_workflowMessage(self, obj):
        return self._wf(obj)['workflowMessage']

    def get_progressPercent(self, obj):
        return self._wf(obj)['progressPercent']

    def get_workflowWarnings(self, obj):
        return self._wf(obj)['workflowWarnings']

    def get_readyForReview(self, obj):
        return self._wf(obj)['readyForReview']

    def get_reviewReadyNotifiedAt(self, obj):
        return self._wf(obj)['reviewReadyNotifiedAt']

    def get_pendingExercises(self, obj):
        return self._wf(obj)['pendingExercises']

    class Meta:
        model = ClassCreationSession
        fields = [
            'id',
            'status',
            'pipeline_type',
            'title',
            'description',
            'source_type',
            'source_page_count',
            'source_mime_type',
            'source_original_name',
            'transcript_markdown',
            'created_at',
            'workflowStage',
            'workflowMessage',
            'progressPercent',
            'workflowWarnings',
            'readyForReview',
            'reviewReadyNotifiedAt',
            'pendingExercises',
        ]


class ExamPrepStep2StructureRequestSerializer(serializers.Serializer):
    """Request serializer for Exam Prep Step 2: Q&A Extraction."""
    session_id = serializers.IntegerField(min_value=1)


class ExamPrepStep2StructureResponseSerializer(serializers.ModelSerializer):
    """Response serializer for Exam Prep Step 2: Q&A Extraction."""
    class Meta:
        model = ClassCreationSession
        fields = [
            'id',
            'status',
            'pipeline_type',
            'title',
            'description',
            'exam_prep_json',
            'created_at',
        ]


class ExamPrepSessionDetailSerializer(serializers.ModelSerializer):
    """Detail serializer for Exam Prep sessions."""
    exam_prep_data = serializers.SerializerMethodField()
    invites_count = serializers.SerializerMethodField()
    organization_id = serializers.IntegerField(read_only=True, allow_null=True)
    workflowStage = serializers.SerializerMethodField()
    workflowMessage = serializers.SerializerMethodField()
    progressPercent = serializers.SerializerMethodField()
    workflowWarnings = serializers.SerializerMethodField()
    readyForReview = serializers.SerializerMethodField()
    reviewReadyNotifiedAt = serializers.SerializerMethodField()
    pendingExercises = serializers.SerializerMethodField()

    @extend_schema_field(serializers.DictField())
    def get_exam_prep_data(self, obj: ClassCreationSession):
        """Parse and return exam_prep_json as dict."""
        raw = obj.exam_prep_json or ''
        if not raw.strip():
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None

    def get_invites_count(self, obj: ClassCreationSession) -> int:
        if hasattr(obj, '_invites_count'):
            return obj._invites_count
        teacher_phone = (getattr(obj.teacher, 'phone', '') or '').strip()
        invites = obj.invites.exclude(phone=teacher_phone) if teacher_phone else obj.invites
        return invites.values('phone').distinct().count()

    def _wf(self, obj):
        return serialize_session_workflow_fields(obj)

    def get_workflowStage(self, obj):
        return self._wf(obj)['workflowStage']

    def get_workflowMessage(self, obj):
        return self._wf(obj)['workflowMessage']

    def get_progressPercent(self, obj):
        return self._wf(obj)['progressPercent']

    def get_workflowWarnings(self, obj):
        return self._wf(obj)['workflowWarnings']

    def get_readyForReview(self, obj):
        return self._wf(obj)['readyForReview']

    def get_reviewReadyNotifiedAt(self, obj):
        return self._wf(obj)['reviewReadyNotifiedAt']

    def get_pendingExercises(self, obj):
        return self._wf(obj)['pendingExercises']

    class Meta:
        model = ClassCreationSession
        fields = [
            'id',
            'status',
            'pipeline_type',
            'title',
            'description',
            'level',
            'duration',
            'source_type',
            'source_page_count',
            'transcript_markdown',
            'exam_prep_json',
            'exam_prep_data',
            'invites_count',
            'organization_id',
            'is_published',
            'published_at',
            'error_detail',
            'created_at',
            'updated_at',
            'workflowStage',
            'workflowMessage',
            'progressPercent',
            'workflowWarnings',
            'readyForReview',
            'reviewReadyNotifiedAt',
            'pendingExercises',
        ]


class ExamPrepSessionUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    level = serializers.CharField(required=False, allow_blank=True)
    duration = serializers.CharField(required=False, allow_blank=True)
    exam_prep_json = serializers.JSONField(required=False)

    def validate_exam_prep_json(self, value):
        """Allow either object/array (JSON) or a valid JSON string."""
        if isinstance(value, str):
            s = value.strip()
            if not s:
                return ''
            try:
                json.loads(s)
            except Exception:
                raise serializers.ValidationError('Invalid JSON string.')
            return s

        try:
            return json.dumps(value, ensure_ascii=False)
        except Exception:
            raise serializers.ValidationError('Invalid JSON payload.')


# ==========================================================================
# STUDENT EXAM PREP SERIALIZERS
# ==========================================================================


class StudentExamPrepListSerializer(serializers.Serializer):
    """Serializer for listing exam preps available to students."""
    id = serializers.IntegerField()
    title = serializers.CharField()
    description = serializers.CharField(allow_blank=True)
    tags = serializers.ListField(child=serializers.CharField(), allow_empty=True)
    questions = serializers.IntegerField()
    createdAt = serializers.CharField(required=False, allow_blank=True)
    instructor = serializers.CharField(required=False, allow_blank=True)
    sourceType = serializers.CharField(required=False, allow_blank=True)


class StudentExamPrepQuestionSerializer(serializers.Serializer):
    """Serializer for exam prep questions exposed to students."""
    question_id = serializers.CharField()
    question_text_markdown = serializers.CharField()
    options = serializers.ListField(child=serializers.DictField())


class StudentExamPrepDetailSerializer(serializers.Serializer):
    """Serializer for student exam prep detail."""
    id = serializers.IntegerField()
    title = serializers.CharField()
    description = serializers.CharField(allow_blank=True)
    questions = StudentExamPrepQuestionSerializer(many=True)
    totalQuestions = serializers.IntegerField()
    subject = serializers.CharField(required=False, allow_blank=True)


class StudentExamPrepSubmitRequestSerializer(serializers.Serializer):
    answers = serializers.DictField(child=serializers.CharField(allow_blank=True), required=False, default=dict)
    finalize = serializers.BooleanField(required=False, default=False)


class StudentExamPrepSubmitResponseSerializer(serializers.Serializer):
    score_0_100 = serializers.IntegerField()
    correct_count = serializers.IntegerField()
    total_questions = serializers.IntegerField()
    finalized = serializers.BooleanField()


class StudentExamPrepResultItemSerializer(serializers.Serializer):
    question_id = serializers.CharField()
    selected_label = serializers.CharField(allow_blank=True)
    is_correct = serializers.BooleanField()
    attempts = serializers.IntegerField(required=False, default=0)
    score_for_question = serializers.IntegerField(required=False, default=0)


class StudentExamPrepResultResponseSerializer(serializers.Serializer):
    finalized = serializers.BooleanField()
    score_0_100 = serializers.IntegerField()
    correct_count = serializers.IntegerField()
    total_questions = serializers.IntegerField()
    answers = serializers.DictField(child=serializers.CharField(allow_blank=True))
    items = StudentExamPrepResultItemSerializer(many=True)


# ---------------------------------------------------------------------------
# Per-question check-answer (exam prep)
# ---------------------------------------------------------------------------

class StudentExamPrepCheckAnswerRequestSerializer(serializers.Serializer):
    question_id = serializers.CharField()
    answer = serializers.CharField(allow_blank=True)


class StudentExamPrepCheckAnswerResponseSerializer(serializers.Serializer):
    is_correct = serializers.BooleanField()
    attempts = serializers.IntegerField()
    hint = serializers.CharField(allow_blank=True, required=False, default='')
    encouragement = serializers.CharField(allow_blank=True, required=False, default='')
    score_for_question = serializers.IntegerField(required=False, default=0)
