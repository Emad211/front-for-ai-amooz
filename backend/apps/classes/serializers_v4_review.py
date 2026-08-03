from rest_framework import serializers

from apps.classes.models_v4_review import ExamReviewDecision


class ExamPrepV4ReviewDecisionSerializer(serializers.Serializer):
    matchDecisionId = serializers.IntegerField(min_value=1)
    action = serializers.ChoiceField(choices=ExamReviewDecision.Action.values)
    questionRecordId = serializers.IntegerField(
        min_value=1,
        required=False,
        allow_null=True,
    )
    note = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
        trim_whitespace=True,
    )

    def validate(self, attrs):
        action = attrs['action']
        question_id = attrs.get('questionRecordId')
        if action == ExamReviewDecision.Action.MATCH and not question_id:
            raise serializers.ValidationError(
                {'questionRecordId': 'برای اتصال دستی، سؤال مقصد را انتخاب کنید.'}
            )
        if action != ExamReviewDecision.Action.MATCH and question_id is not None:
            raise serializers.ValidationError(
                {'questionRecordId': 'این عملیات نباید سؤال مقصد داشته باشد.'}
            )
        return attrs


class ExamPrepV4ReviewFinalizeSerializer(serializers.Serializer):
    questionSetFingerprint = serializers.RegexField(r'^[0-9a-f]{64}$')
    answerSetFingerprint = serializers.RegexField(r'^[0-9a-f]{64}$')
