import json

from django.conf import settings
from rest_framework import serializers

from drf_spectacular.utils import extend_schema_field

from .models import ClassAnnouncement, ClassCreationSession, ClassInvitation, ClassPrerequisite


class Step1TranscribeRequestSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True)
    file = serializers.FileField()
    client_request_id = serializers.UUIDField(required=False)
    run_full_pipeline = serializers.BooleanField(required=False, default=False)

    def validate_file(self, value):
        max_bytes = getattr(settings, 'TRANSCRIPTION_MAX_UPLOAD_BYTES', 500 * 1024 * 1024)
        max_mb = max_bytes // (1024 * 1024)
        if getattr(value, 'size', 0) > max_bytes:
            raise serializers.ValidationError(f'File is too large (max {max_mb}MB).')

        content_type = getattr(value, 'content_type', '') or ''
        if not (content_type.startswith('audio/') or content_type.startswith('video/')):
            raise serializers.ValidationError('Only audio/video uploads are supported for transcription.')

        return value


class Step1TranscribeResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClassCreationSession
        fields = [
            'id',
            'status',
            'title',
            'description',
            'source_mime_type',
            'source_original_name',
            'transcript_markdown',
            'created_at',
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

    class Meta:
        model = ClassCreationSession
        fields = [
            'id',
            'status',
            'title',
            'description',
            'is_published',
            'published_at',
            'invites_count',
            'lessons_count',
            'created_at',
            'updated_at',
        ]


class ClassCreationSessionDetailSerializer(serializers.ModelSerializer):
    invites_count = serializers.SerializerMethodField()

    def get_invites_count(self, obj: ClassCreationSession) -> int:
        # Prefer the annotation if available (from list views), otherwise fall back.
        if hasattr(obj, '_invites_count'):
            return obj._invites_count
        return obj.invites.count()

    class Meta:
        model = ClassCreationSession
        fields = [
            'id',
            'status',
            'title',
            'description',
            'level',
            'duration',
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
            digits = ''.join(ch for ch in str(raw) if ch.isdigit())
            if digits.startswith('98') and len(digits) == 12:
                digits = '0' + digits[2:]
            if len(digits) == 10 and digits.startswith('9'):
                digits = '0' + digits
            if not digits.startswith('09') or len(digits) != 11:
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

    def validate_file(self, value):
        max_bytes = getattr(settings, 'TRANSCRIPTION_MAX_UPLOAD_BYTES', 500 * 1024 * 1024)
        max_mb = max_bytes // (1024 * 1024)
        if getattr(value, 'size', 0) > max_bytes:
            raise serializers.ValidationError(f'File is too large (max {max_mb}MB).')

        content_type = getattr(value, 'content_type', '') or ''
        if not (content_type.startswith('audio/') or content_type.startswith('video/')):
            raise serializers.ValidationError('Only audio/video uploads are supported for transcription.')

        return value


class ExamPrepStep1TranscribeResponseSerializer(serializers.ModelSerializer):
    """Response serializer for Exam Prep Step 1: Transcription."""
    class Meta:
        model = ClassCreationSession
        fields = [
            'id',
            'status',
            'pipeline_type',
            'title',
            'description',
            'source_mime_type',
            'source_original_name',
            'transcript_markdown',
            'created_at',
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
        return obj.invites.count()

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
            'transcript_markdown',
            'exam_prep_json',
            'exam_prep_data',
            'invites_count',
            'is_published',
            'published_at',
            'error_detail',
            'created_at',
            'updated_at',
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


class StudentExamPrepResultResponseSerializer(serializers.Serializer):
    finalized = serializers.BooleanField()
    score_0_100 = serializers.IntegerField()
    correct_count = serializers.IntegerField()
    total_questions = serializers.IntegerField()
    answers = serializers.DictField(child=serializers.CharField(allow_blank=True))
    items = StudentExamPrepResultItemSerializer(many=True)
