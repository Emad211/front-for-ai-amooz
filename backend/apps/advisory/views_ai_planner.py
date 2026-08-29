"""Risman steps 5+6 (wave R3) — the AI plan-draft door.

One endpoint, two transports: JSON ``{prompt}`` (text) and multipart
``voice=true`` + ``audio=<file>`` (voice → transcription → the same text path).
Tenancy goes through ``scope.advisor_engagement`` (stranger ⇒ 404, ق۶); role
gating is ``IsAdvisorUser``; provider failures are the pinned 502 so the
advisor sees «سرویس هوش مصنوعی در دسترس نیست.» instead of a stack trace.
"""

from django.urls import path

from rest_framework import parsers, status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.advisory.serializers import StudyPlanOutSerializer
from apps.advisory.services import ai_planner, scope
from apps.core.permissions import IsAdvisorUser


class AdvisorAIDraftPlanView(APIView):
    permission_classes = [IsAuthenticated, IsAdvisorUser]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    def post(self, request, pk: int):
        engagement = scope.advisor_engagement(request.user, pk)
        if engagement is None:
            raise NotFound('همکاری مشاوره‌ای یافت نشد.')

        voice = str(request.data.get('voice') or '').lower() in ('true', '1', 'yes')
        try:
            if voice:
                upload = request.FILES.get('audio')
                if upload is None:
                    raise ai_planner.AudioMissing()
                plan = ai_planner.draft_plan_from_voice(
                    engagement,
                    data=upload.read(),
                    mime_type=(getattr(upload, 'content_type', '') or ''),
                )
            else:
                plan = ai_planner.draft_plan_from_text(
                    engagement,
                    request.data.get('prompt') or '',
                )
        except ai_planner.AIUnavailable as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        except ai_planner.AIPlannerError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                'detail': 'پیش‌نویس برنامه ساخته شد؛ بازبینی کن و بعد منتشرش کن.',
                'plan': StudyPlanOutSerializer(plan).data,
            },
            status=status.HTTP_201_CREATED,
        )


urlpatterns = [
    path(
        'students/<int:pk>/plans/ai-draft/',
        AdvisorAIDraftPlanView.as_view(),
        name='advisory_ai_plan_draft',
    ),
]
