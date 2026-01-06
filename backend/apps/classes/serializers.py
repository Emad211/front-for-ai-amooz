from rest_framework import serializers
import json

from drf_spectacular.utils import extend_schema_field

from .models import ClassCreationSession, ClassInvitation, ClassPrerequisite


class Step1TranscribeRequestSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True)
    file = serializers.FileField()
    client_request_id = serializers.UUIDField(required=False)
    run_full_pipeline = serializers.BooleanField(required=False, default=False)

    def validate_file(self, value):
        max_bytes = 50 * 1024 * 1024
        if getattr(value, 'size', 0) > max_bytes:
            raise serializers.ValidationError('File is too large (max 50MB).')

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
    invites_count = serializers.SerializerMethodField()

    def get_invites_count(self, obj: ClassCreationSession) -> int:
        return obj.invites.count()

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
            'created_at',
            'updated_at',
        ]


class ClassCreationSessionDetailSerializer(serializers.ModelSerializer):
    invites_count = serializers.SerializerMethodField()

    def get_invites_count(self, obj: ClassCreationSession) -> int:
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
    id = serializers.IntegerField()
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
