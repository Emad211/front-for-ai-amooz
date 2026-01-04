from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.serializers import MeSerializer

from .serializers import RegisterSerializer, LogoutSerializer


class RegisterView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                'user': MeSerializer(user).data,
                'tokens': {
                    'access': str(refresh.access_token),
                    'refresh': str(refresh),
                },
            },
            status=status.HTTP_201_CREATED,
        )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        refresh_token = RefreshToken(serializer.validated_data['refresh'])
        token_user_id = refresh_token.get('user_id')
        if token_user_id is None or str(token_user_id) != str(request.user.id):
            raise PermissionDenied('Refresh token does not belong to the current user.')

        refresh_token.blacklist()
        return Response(status=status.HTTP_205_RESET_CONTENT)
