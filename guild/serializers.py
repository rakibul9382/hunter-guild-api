from rest_framework import serializers
from .models import Task, TaskAssignment, HunterProfile, User, OTPRecord, Notification
from django.contrib.auth.password_validation import validate_password
from phonenumber_field.serializerfields import PhoneNumberField
from django.db import transaction
from django.core.cache import cache

class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = '__all__'


class HunterProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = HunterProfile
        fields = '__all__'


class TaskAssignmentSerializer(serializers.ModelSerializer):

    task = TaskSerializer(read_only=True)

    class Meta:
        model = TaskAssignment
        fields = ['id', 'status', 'task', 'hunter']


class HunterSignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password]
    )
    confirm_password = serializers.CharField(
        write_only=True,
        required=True
    )

    class Meta:
        model = User
        fields = [
            'username',
            'email',
            'phone_number',
            'profile_image',
            'password',
            'confirm_password'
        ]

    def validate(self, attrs):
        password = attrs.get('password')
        confirm_password = attrs.get('confirm_password')
        if password != confirm_password:
            raise serializers.ValidationError({
                'confirm_password': "Password dont match."
            })
        return attrs

    def create(self, validated_data):
        validated_data.pop('confirm_password', None)
        validated_data['is_active'] = False
        return User.objects.create_user(**validated_data)


class OtpSerializer(serializers.ModelSerializer):
    class Meta:
        model = OTPRecord
        field = '__all__'


class AdminSignupSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'username',
            'email',
            'phone_number',
            'password',
            'confirm_password'
        ]
        extra_kwargs = {
            'password': {'write_only': True},
            'confirm_password': {'write_only': True}
        }

    def validate(self, attrs):
        password = attrs.get('password')
        confirm_password = attrs.get('confirm_password')
        if password != confirm_password:
            raise serializers.ValidationError({
                'confirm_password': "Confirm password Don't match."
            })
        return attrs

    def create(self, validated_data):
        validated_data.pop('confirm_password', None)
        validated_data['is_staff'] = True
        validated_data['is_active'] = True
        return User.objects.create_user(**validated_data)


class TaskCreationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = [
            'title',
            'description',
            'category',
            'priority',
            'reward_amount',
            'required_level',
            'deadline',
            'status',
        ]
        read_only_fields = ['created_by']


class TaskSubmissionProof(serializers.ModelSerializer):
    class Meta:
        model = TaskAssignment
        fields = ['completion_proof']


class TaskReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskAssignment
        fields = ['admin_notes', 'status']


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['username', 'email', 'phone_number', 'profile_image']


class ProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = HunterProfile
        fields = [
            'user',
            'level',
            'experience_points',
            'total_completed_contract',
            'total_failed_contract',
            'availability_status',
            'rating',
            'location',
            'created_at'
        ]


class NotificationSerializer(serializers.ModelSerializer):

    class Meta:
        model = Notification
        fields = ['recipient', 'message', 'created_at']


class ContractHistorySerializer(serializers.ModelSerializer):

    task = TaskSerializer(read_only=True)

    class Meta:
        model = TaskAssignment
        fields = ['id', 'status', 'task', 'submitted_at', 'admin_notes']


class EditProfileSerializer(serializers.ModelSerializer):
    #access from user model
    phone_number = PhoneNumberField(source='user.phone_number', required=False)
    profile_image = serializers.ImageField(source='user.profile_image', required=False)
    email = serializers.EmailField(source='user.email', required=False)
    otp = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = HunterProfile
        fields = ['location', 'availability_status', 'phone_number', 'profile_image', 'email', 'otp']

    def validate(self, attrs):
        user_data = attrs.get('user', {})

        sensitive_data = ('phone_number' in user_data or 'email' in user_data)
        if sensitive_data:
            otp_provided = attrs.get('otp')
            if not otp_provided:
                raise serializers.ValidationError({
                    "otp": "An OTP is required to change your email or phone number."
                })
            # Acccess from cache
            user_id = self.context['request'].user.id  # we can also acces through self.instance
            saved_otp = cache.get(f"otp_{user_id}")

            if not saved_otp or otp_provided != saved_otp:
                raise serializers.ValidationError({
                    "otp": "Invalid or expired OTP."
                })
        return attrs

    @transaction.atomic
    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', {})
        user = instance.user

        if 'phone_number' in user_data:
            user.phone_number = user_data['phone_number']
        if 'profile_image' in user_data:
            user.profile_image = user_data['profile_image']
        if 'email' in user_data:
            user.email = user_data['email']
        user.save()

        instance.location = validated_data.get('location', instance.location)
        instance.availability_status = validated_data.get('availability_status', instance.availability_status)
        instance.save()

        return instance
