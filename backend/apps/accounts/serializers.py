from rest_framework import serializers

class MeSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True, help_text="Unique ID of the user.")
    username = serializers.CharField(read_only=True, help_text="Username of the user.")
    email = serializers.EmailField(read_only=True, help_text="Email address of the user.")
    role = serializers.CharField(read_only=True, help_text="Role of the user (student/teacher/admin).")
    is_profile_completed = serializers.BooleanField(read_only=True, help_text="Indicates if the user has completed their profile.")
