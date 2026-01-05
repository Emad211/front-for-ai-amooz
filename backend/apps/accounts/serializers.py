from rest_framework import serializers

class MeSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True, help_text="Unique ID of the user.")
    username = serializers.CharField(read_only=True, help_text="Username of the user.")
    first_name = serializers.CharField(read_only=True, help_text="First name of the user.")
    email = serializers.EmailField(read_only=True, help_text="Email address of the user.")
    phone = serializers.CharField(read_only=True, allow_null=True, help_text="Phone number of the user.")
    avatar = serializers.ImageField(read_only=True, allow_null=True, help_text="Avatar image.")
    role = serializers.CharField(read_only=True, help_text="Role of the user (student/teacher/admin).")
    is_profile_completed = serializers.BooleanField(read_only=True, help_text="Indicates if the user has completed their profile.")


class MeUpdateSerializer(serializers.Serializer):
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    phone = serializers.CharField(required=False, allow_blank=True, max_length=15)

    def update(self, instance, validated_data):
        for field in ['first_name', 'last_name', 'phone']:
            if field in validated_data:
                value = validated_data.get(field)
                if field == 'phone':
                    value = (value or '').strip() or None
                setattr(instance, field, value)
        update_fields = list(validated_data.keys())
        if update_fields:
            instance.save(update_fields=update_fields)
        else:
            instance.save()
        return instance
